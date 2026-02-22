"""
PBIR Report Builder for Fabric Git Integration.

Generates PBIR (Power BI Report) files that reference a semantic model via byPath.
Creates reports with pages, visuals, and proper schema references.

Usage:
    from fabric_mcp.report_builder import ReportBuilder
    
    builder = ReportBuilder(
        report_name="Sales Report",
        semantic_model_name="Sales Model"  # Will use ../Sales Model.SemanticModel
    )
    
    # Add a page with visuals
    builder.add_page("Overview", [
        builder.card("Total Revenue", "Sales", "Total Revenue", x=20, y=20),
        builder.bar_chart("Sales by Region", "Sales", "Region", "Revenue", x=20, y=180),
    ])
    
    files = builder.build_all_files()  # Returns dict of {path: content}
"""

import json
import uuid
from typing import Dict, List, Optional, Any

# Schema URLs
FABRIC_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric"
PLATFORM_SCHEMA = f"{FABRIC_SCHEMA}/gitIntegration/platformProperties/2.0.0/schema.json"
PBIR_SCHEMA = f"{FABRIC_SCHEMA}/item/report/definitionProperties/2.0.0/schema.json"
RPT = f"{FABRIC_SCHEMA}/item/report/definition"


class ReportBuilder:
    """Builds PBIR report files for Fabric Git integration."""
    
    def __init__(
        self,
        report_name: str,
        semantic_model_name: Optional[str] = None,
        theme_name: str = "CY25SU10"
    ):
        """
        Initialize the report builder.
        
        Args:
            report_name: Display name for the report
            semantic_model_name: Name of the semantic model to reference via byPath
                                If None, creates a report with no data connection
            theme_name: Base theme name (default: CY25SU10)
        """
        self.report_name = report_name
        self.semantic_model_name = semantic_model_name
        self.theme_name = theme_name
        
        self._pages: Dict[str, Dict[str, Any]] = {}
        self._visual_counter = 0
    
    def _vid(self) -> str:
        """Generate a unique visual ID."""
        self._visual_counter += 1
        return f"v{self._visual_counter:04d}"
    
    def _page_id(self) -> str:
        """Generate a unique page ID."""
        return f"ReportSection{uuid.uuid4().hex[:8]}"
    
    # =========================================================================
    # Field Reference Helpers
    # =========================================================================
    
    @staticmethod
    def _col(table: str, column: str) -> Dict:
        """Create a column field reference."""
        return {
            "Column": {
                "Expression": {"SourceRef": {"Entity": table}},
                "Property": column
            }
        }
    
    @staticmethod
    def _measure(table: str, measure: str) -> Dict:
        """Create a measure field reference."""
        return {
            "Measure": {
                "Expression": {"SourceRef": {"Entity": table}},
                "Property": measure
            }
        }
    
    @staticmethod
    def _agg(table: str, column: str, func: str) -> Dict:
        """Create an aggregated column reference."""
        # Map string to numeric function code
        func_map = {
            "Sum": 0, "sum": 0,
            "Average": 1, "Avg": 1, "average": 1, "avg": 1,
            "Count": 2, "DistinctCount": 2, "count": 2, "distinctcount": 2,
            "Min": 3, "min": 3,
            "Max": 4, "max": 4,
        }
        func_code = func_map.get(func, 0)  # Default to Sum
        
        return {
            "Aggregation": {
                "Expression": {
                    "Column": {
                        "Expression": {"SourceRef": {"Entity": table}},
                        "Property": column
                    }
                },
                "Function": func_code
            }
        }
    
    def _title_obj(self, text: str) -> Dict:
        """Create a title object for a visual."""
        return {
            "title": [{
                "properties": {
                    "show": {"expr": {"Literal": {"Value": "true"}}},
                    "text": {"expr": {"Literal": {"Value": f"'{text}'"}}}
                }
            }]
        }
    
    # =========================================================================
    # Visual Builders
    # =========================================================================
    
    def card(
        self,
        title: str,
        table: str,
        measure: str,
        x: int = 0,
        y: int = 0,
        width: int = 280,
        height: int = 140
    ) -> Dict:
        """
        Create a card visual showing a single measure.
        
        Args:
            title: Visual title
            table: Table containing the measure
            measure: Measure name
            x, y: Position
            width, height: Size
        """
        name = self._vid()
        return {
            "$schema": f"{RPT}/visualContainer/2.5.0/schema.json",
            "name": name,
            "position": {"x": x, "y": y, "width": width, "height": height, "z": 0, "tabOrder": 0},
            "visual": {
                "visualType": "card",
                "query": {
                    "queryState": {
                        "Values": {
                            "projections": [{
                                "field": self._measure(table, measure),
                                "queryRef": f"{table}.{measure}",
                                "nativeQueryRef": measure,
                                "active": True
                            }]
                        }
                    }
                },
                "objects": {
                    "labels": [{
                        "properties": {
                            "labelDisplayUnits": {"expr": {"Literal": {"Value": "1D"}}},
                            "fontSize": {"expr": {"Literal": {"Value": "12D"}}}
                        }
                    }]
                },
                "visualContainerObjects": self._title_obj(title),
                "drillFilterOtherVisuals": True,
            }
        }
    
    def bar_chart(
        self,
        title: str,
        table: str,
        category_column: str,
        value_column: str,
        aggregation: str = "Sum",
        x: int = 0,
        y: int = 0,
        width: int = 600,
        height: int = 400
    ) -> Dict:
        """
        Create a clustered bar chart.
        
        Args:
            title: Visual title
            table: Table name
            category_column: Column for categories (Y axis)
            value_column: Column for values (X axis)
            aggregation: Aggregation function (Sum, Count, Average, Min, Max)
            x, y: Position
            width, height: Size
        """
        name = self._vid()
        return {
            "$schema": f"{RPT}/visualContainer/2.5.0/schema.json",
            "name": name,
            "position": {"x": x, "y": y, "width": width, "height": height, "z": 0, "tabOrder": 0},
            "visual": {
                "visualType": "clusteredBarChart",
                "query": {
                    "queryState": {
                        "Category": {
                            "projections": [{
                                "field": self._col(table, category_column),
                                "queryRef": f"{table}.{category_column}",
                                "nativeQueryRef": category_column,
                                "active": True
                            }]
                        },
                        "Y": {
                            "projections": [{
                                "field": self._agg(table, value_column, aggregation),
                                "queryRef": f"{aggregation}({table}.{value_column})",
                                "nativeQueryRef": f"{aggregation} of {value_column}",
                                "active": True
                            }]
                        }
                    }
                },
                "visualContainerObjects": self._title_obj(title),
                "drillFilterOtherVisuals": True,
            }
        }
    
    def line_chart(
        self,
        title: str,
        table: str,
        category_column: str,
        value_column: str,
        aggregation: str = "Sum",
        x: int = 0,
        y: int = 0,
        width: int = 600,
        height: int = 400
    ) -> Dict:
        """
        Create a line chart for trends.
        
        Args:
            title: Visual title
            table: Table name
            category_column: Column for X axis (typically date)
            value_column: Column for Y axis values
            aggregation: Aggregation function
            x, y: Position
            width, height: Size
        """
        name = self._vid()
        return {
            "$schema": f"{RPT}/visualContainer/2.5.0/schema.json",
            "name": name,
            "position": {"x": x, "y": y, "width": width, "height": height, "z": 0, "tabOrder": 0},
            "visual": {
                "visualType": "lineChart",
                "query": {
                    "queryState": {
                        "Category": {
                            "projections": [{
                                "field": self._col(table, category_column),
                                "queryRef": f"{table}.{category_column}",
                                "nativeQueryRef": category_column,
                                "active": True
                            }]
                        },
                        "Y": {
                            "projections": [{
                                "field": self._agg(table, value_column, aggregation),
                                "queryRef": f"{aggregation}({table}.{value_column})",
                                "nativeQueryRef": f"{aggregation} of {value_column}",
                                "active": True
                            }]
                        }
                    }
                },
                "visualContainerObjects": self._title_obj(title),
                "drillFilterOtherVisuals": True,
            }
        }
    
    def table_visual(
        self,
        title: str,
        table: str,
        columns: List[str],
        x: int = 0,
        y: int = 0,
        width: int = 600,
        height: int = 400
    ) -> Dict:
        """
        Create a table visual.
        
        Args:
            title: Visual title
            table: Table name
            columns: List of column names to display
            x, y: Position
            width, height: Size
        """
        name = self._vid()
        projections = []
        for col in columns:
            projections.append({
                "field": self._col(table, col),
                "queryRef": f"{table}.{col}",
                "nativeQueryRef": col,
                "active": True
            })
        
        return {
            "$schema": f"{RPT}/visualContainer/2.5.0/schema.json",
            "name": name,
            "position": {"x": x, "y": y, "width": width, "height": height, "z": 0, "tabOrder": 0},
            "visual": {
                "visualType": "tableEx",
                "query": {
                    "queryState": {
                        "Values": {"projections": projections}
                    }
                },
                "visualContainerObjects": self._title_obj(title),
                "drillFilterOtherVisuals": True,
            }
        }
    
    def slicer(
        self,
        title: str,
        table: str,
        column: str,
        x: int = 0,
        y: int = 0,
        width: int = 200,
        height: int = 300
    ) -> Dict:
        """
        Create a slicer for filtering.
        
        Args:
            title: Visual title
            table: Table name
            column: Column to filter by
            x, y: Position
            width, height: Size
        """
        name = self._vid()
        return {
            "$schema": f"{RPT}/visualContainer/2.5.0/schema.json",
            "name": name,
            "position": {"x": x, "y": y, "width": width, "height": height, "z": 0, "tabOrder": 0},
            "visual": {
                "visualType": "slicer",
                "query": {
                    "queryState": {
                        "Values": {
                            "projections": [{
                                "field": self._col(table, column),
                                "queryRef": f"{table}.{column}",
                                "nativeQueryRef": column,
                                "active": True
                            }]
                        }
                    }
                },
                "visualContainerObjects": self._title_obj(title),
            }
        }
    
    # =========================================================================
    # Page Management
    # =========================================================================
    
    def add_page(
        self,
        display_name: str,
        visuals: List[Dict],
        width: int = 1280,
        height: int = 720
    ) -> "ReportBuilder":
        """
        Add a page with visuals to the report.
        
        Args:
            display_name: Page display name
            visuals: List of visual definitions (from card(), bar_chart(), etc.)
            width: Page width
            height: Page height
        """
        page_id = self._page_id()
        
        self._pages[page_id] = {
            "page": {
                "$schema": f"{RPT}/page/2.3.0/schema.json",
                "name": page_id,
                "displayName": display_name,
                "displayOption": "FitToPage",
                "width": width,
                "height": height,
            },
            "visuals": {v["name"]: v for v in visuals}
        }
        
        return self
    
    def add_blank_page(self, display_name: str = "Page 1") -> "ReportBuilder":
        """Add a blank page with no visuals."""
        return self.add_page(display_name, [])
    
    # =========================================================================
    # Build Output
    # =========================================================================
    
    def build_all_files(self) -> Dict[str, str]:
        """
        Build all PBIR files for the report.
        
        Returns:
            Dict mapping relative file paths to file contents
        """
        # Ensure at least one page exists
        if not self._pages:
            self.add_blank_page()
        
        files = {}
        
        # .platform metadata
        files[".platform"] = json.dumps({
            "$schema": PLATFORM_SCHEMA,
            "metadata": {"type": "Report", "displayName": self.report_name},
            "config": {"version": "2.0", "logicalId": str(uuid.uuid4())},
        }, indent=2)
        
        # definition.pbir - references semantic model via byPath
        pbir_content = {
            "$schema": PBIR_SCHEMA,
            "version": "4.0",
            "datasetReference": {}
        }
        
        if self.semantic_model_name:
            pbir_content["datasetReference"]["byPath"] = {
                "path": f"../{self.semantic_model_name}.SemanticModel"
            }
        else:
            pbir_content["datasetReference"]["byPath"] = None
            pbir_content["datasetReference"]["byConnection"] = None
        
        files["definition.pbir"] = json.dumps(pbir_content, indent=2)
        
        # definition/report.json - theme configuration
        files["definition/report.json"] = json.dumps({
            "$schema": f"{RPT}/report/3.1.0/schema.json",
            "themeCollection": {
                "baseTheme": {
                    "name": self.theme_name,
                    "reportVersionAtImport": {
                        "visual": "2.1.0",
                        "report": "3.0.0",
                        "page": "2.3.0",
                    },
                    "type": "SharedResources",
                }
            },
        }, indent=2)
        
        # definition/version.json
        files["definition/version.json"] = json.dumps({
            "$schema": f"{RPT}/versionMetadata/1.0.0/schema.json",
            "version": "2.0.0",
        }, indent=2)
        
        # Pages and visuals
        for page_id, page_data in self._pages.items():
            files[f"definition/pages/{page_id}/page.json"] = json.dumps(
                page_data["page"], indent=2
            )
            for vid, visual in page_data["visuals"].items():
                files[f"definition/pages/{page_id}/visuals/{vid}/visual.json"] = json.dumps(
                    visual, indent=2
                )
        
        return files
