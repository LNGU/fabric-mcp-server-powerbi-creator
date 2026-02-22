"""
TMDL Semantic Model Builder for Direct Lake.

Generates TMDL (Tabular Model Definition Language) files for Fabric Git integration.
Creates semantic models that connect to Lakehouse tables via Direct Lake mode.

Usage:
    from fabric_mcp.semantic_model import SemanticModelBuilder
    
    builder = SemanticModelBuilder(
        model_name="My Model",
        lakehouse_workspace_id="workspace-guid",
        lakehouse_id="lakehouse-guid"
    )
    builder.add_table("Sales", [
        {"name": "Date", "dataType": "DateTime"},
        {"name": "Revenue", "dataType": "Double"},
    ])
    builder.add_measure("Sales", "Total Revenue", "SUM(Sales[Revenue])", "#,##0")
    builder.add_relationship("Sales", "DateKey", "Calendar", "DateKey")
    
    files = builder.build_all_files()  # Returns dict of {path: content}
"""

import json
import uuid
from typing import Dict, List, Optional, Any

# Schema URLs
FABRIC_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric"
PLATFORM_SCHEMA = f"{FABRIC_SCHEMA}/gitIntegration/platformProperties/2.0.0/schema.json"
PBISM_SCHEMA = f"{FABRIC_SCHEMA}/item/semanticModel/definitionProperties/1.0.0/schema.json"

# TMDL type mapping from Power BI types
TMDL_TYPE_MAP = {
    "DateTime": "dateTime",
    "Int64": "int64",
    "String": "string",
    "Double": "double",
    "Boolean": "boolean",
    "Decimal": "decimal",
    # Lowercase variants
    "datetime": "dateTime",
    "int64": "int64",
    "string": "string",
    "double": "double",
    "boolean": "boolean",
    "decimal": "decimal",
}


class SemanticModelBuilder:
    """Builds TMDL semantic model files for Fabric Git integration."""
    
    def __init__(
        self,
        model_name: str,
        lakehouse_workspace_id: str,
        lakehouse_id: str,
        onelake_url: str = "https://onelake.dfs.fabric.microsoft.com"
    ):
        """
        Initialize the semantic model builder.
        
        Args:
            model_name: Display name for the semantic model
            lakehouse_workspace_id: Workspace ID containing the lakehouse
            lakehouse_id: Lakehouse ID for Direct Lake connection
            onelake_url: OneLake URL (default: https://onelake.dfs.fabric.microsoft.com)
        """
        self.model_name = model_name
        self.workspace_id = lakehouse_workspace_id
        self.lakehouse_id = lakehouse_id
        self.onelake_url = onelake_url
        
        self._tables: Dict[str, Dict[str, Any]] = {}
        self._measures: Dict[str, List[Dict[str, Any]]] = {}
        self._relationships: List[Dict[str, Any]] = []
        self._guids: Dict[str, str] = {}
    
    def _guid(self, key: Optional[str] = None) -> str:
        """Generate a new GUID, optionally caching by key."""
        g = str(uuid.uuid4())
        if key:
            self._guids[key] = g
        return g
    
    def add_table(self, table_name: str, columns: List[Dict[str, str]]) -> "SemanticModelBuilder":
        """
        Add a table definition.
        
        Args:
            table_name: Name of the table (must match Lakehouse delta table name)
            columns: List of column definitions:
                     [{"name": "column_name", "dataType": "String"}, ...]
                     
        Supported dataTypes: DateTime, Int64, String, Double, Boolean, Decimal
        """
        self._tables[table_name] = {"columns": columns}
        return self
    
    def add_measure(
        self, 
        table_name: str, 
        measure_name: str, 
        expression: str, 
        format_string: Optional[str] = None
    ) -> "SemanticModelBuilder":
        """
        Add a DAX measure to a table.
        
        Args:
            table_name: Table to attach the measure to
            measure_name: Name of the measure
            expression: DAX expression (e.g., "SUM(Sales[Revenue])")
            format_string: Optional format string (e.g., "#,##0", "0.0%")
        """
        if table_name not in self._measures:
            self._measures[table_name] = []
        
        measure = {"name": measure_name, "expression": expression}
        if format_string:
            measure["formatString"] = format_string
        
        self._measures[table_name].append(measure)
        return self
    
    def add_relationship(
        self,
        from_table: str,
        from_column: str,
        to_table: str,
        to_column: str,
        cross_filter: str = "single",
        is_active: bool = True,
        many_to_many: bool = False
    ) -> "SemanticModelBuilder":
        """
        Add a relationship between tables.
        
        Args:
            from_table: Source table (typically fact/many side)
            from_column: Source column
            to_table: Target table (typically dimension/one side)
            to_column: Target column
            cross_filter: "single" or "both" for bi-directional
            is_active: Whether relationship is active (False for inactive)
            many_to_many: True for many-to-many relationships
        """
        self._relationships.append({
            "fromTable": from_table,
            "fromColumn": from_column,
            "toTable": to_table,
            "toColumn": to_column,
            "crossFilteringBehavior": "bothDirections" if cross_filter == "both" else None,
            "isActive": is_active,
            "manyToMany": many_to_many,
        })
        return self
    
    def build_all_files(self) -> Dict[str, str]:
        """
        Build all TMDL files for the semantic model.
        
        Returns:
            Dict mapping relative file paths to file contents
        """
        files = {}
        
        # .platform metadata
        files[".platform"] = json.dumps({
            "$schema": PLATFORM_SCHEMA,
            "metadata": {"type": "SemanticModel", "displayName": self.model_name},
            "config": {"version": "2.0", "logicalId": self._guid("model_logical")},
        }, indent=2)
        
        # definition.pbism
        files["definition.pbism"] = json.dumps({
            "$schema": PBISM_SCHEMA,
            "version": "4.2",
            "settings": {},
        }, indent=2)
        
        # definition/database.tmdl (1604 required for Direct Lake)
        files["definition/database.tmdl"] = "database\n\tcompatibilityLevel: 1604\n"
        
        # definition/model.tmdl
        files["definition/model.tmdl"] = self._build_model_tmdl()
        
        # definition/expressions.tmdl (Direct Lake connection)
        files["definition/expressions.tmdl"] = self._build_expressions_tmdl()
        
        # definition/relationships.tmdl
        if self._relationships:
            files["definition/relationships.tmdl"] = self._build_relationships_tmdl()
        
        # definition/tables/*.tmdl
        for table_name in self._tables:
            measures = self._measures.get(table_name, [])
            files[f"definition/tables/{table_name}.tmdl"] = self._build_table_tmdl(
                table_name, self._tables[table_name], measures
            )
        
        return files
    
    def _build_model_tmdl(self) -> str:
        """Build the model.tmdl file content."""
        lines = [
            "model Model",
            "\tculture: en-US",
            "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
            "\tsourceQueryCulture: en-US",
            "\tdataAccessOptions",
            "\t\tlegacyRedirects",
            "\t\treturnErrorValuesAsNull",
            "",
            'annotation PBI_QueryOrder = ["DirectLake - lakehouse"]',
            "",
            'annotation __PBI_TimeIntelligenceEnabled = 1',
            "",
            'annotation PBI_ProTooling = ["RemoteModeling","DirectLakeOnOneLakeCreatedInDesktop"]',
            "",
        ]
        
        # Reference all tables
        for table_name in self._tables:
            lines.append(f"ref table {table_name}")
        
        lines.append("")
        lines.append("ref expression 'DirectLake - lakehouse'")
        lines.append("")
        lines.append("ref cultureInfo en-US")
        lines.append("")
        
        return "\n".join(lines)
    
    def _build_expressions_tmdl(self) -> str:
        """Build the expressions.tmdl file with Direct Lake connection."""
        lakehouse_path = f"{self.onelake_url}/{self.workspace_id}/{self.lakehouse_id}"
        
        return (
            "expression 'DirectLake - lakehouse' =\n"
            "\t\tlet\n"
            f"\t\t\tSource = AzureStorage.DataLake(\"{lakehouse_path}\", [HierarchicalNavigation=true])\n"
            "\t\tin\n"
            "\t\t\tSource\n"
            f"\tlineageTag: {self._guid('expr_dl')}\n"
            "\n"
            "\tannotation PBI_IncludeFutureArtifacts = False\n"
        )
    
    def _build_relationships_tmdl(self) -> str:
        """Build the relationships.tmdl file content."""
        lines = []
        
        for rel in self._relationships:
            rel_id = self._guid()
            lines.append(f"relationship {rel_id}")
            
            if rel.get("manyToMany"):
                lines.append("\tfromCardinality: many")
                lines.append("\ttoCardinality: many")
            
            lines.append(f"\tfromColumn: {rel['fromTable']}.{rel['fromColumn']}")
            lines.append(f"\ttoColumn: {rel['toTable']}.{rel['toColumn']}")
            
            if rel.get("crossFilteringBehavior"):
                lines.append(f"\tcrossFilteringBehavior: {rel['crossFilteringBehavior']}")
            
            if rel.get("isActive") is False:
                lines.append("\tisActive: false")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def _build_table_tmdl(
        self, 
        table_name: str, 
        table_def: Dict[str, Any], 
        measures: List[Dict[str, Any]]
    ) -> str:
        """Build a table's .tmdl file content."""
        lines = [f"table {table_name}"]
        lines.append(f"\tlineageTag: {self._guid(f'table_{table_name}')}")
        lines.append(f"\tsourceLineageTag: [dbo].[{table_name}]")
        lines.append("")
        
        # Measures
        for m in measures:
            mname = m["name"]
            expr = m["expression"]
            lines.append(f"\tmeasure '{mname}' = {expr}")
            if "formatString" in m:
                lines.append(f"\t\tformatString: {m['formatString']}")
            lines.append(f"\t\tlineageTag: {self._guid(f'measure_{mname}')}")
            lines.append("")
        
        # Columns
        for col in table_def.get("columns", []):
            cname = col["name"]
            dtype = col.get("dataType", "String")
            tmdl_type = TMDL_TYPE_MAP.get(dtype, "string")
            
            lines.append(f"\tcolumn {cname}")
            lines.append(f"\t\tdataType: {tmdl_type}")
            
            # Default format strings
            if tmdl_type == "dateTime":
                lines.append("\t\tformatString: General Date")
            elif tmdl_type in ("int64", "double", "decimal"):
                lines.append("\t\tformatString: 0")
            
            lines.append(f"\t\tlineageTag: {self._guid(f'col_{table_name}_{cname}')}")
            lines.append(f"\t\tsourceLineageTag: {cname}")
            lines.append("\t\tsummarizeBy: none")
            lines.append(f"\t\tsourceColumn: {cname}")
            lines.append("")
            lines.append("\t\tannotation SummarizationSetBy = Automatic")
            lines.append("")
        
        # Partition - Direct Lake entity reference
        lines.append(f"\tpartition {table_name} = entity")
        lines.append("\t\tmode: directLake")
        lines.append("\t\tsource")
        lines.append(f"\t\t\tentityName: {table_name}")
        lines.append("\t\t\texpressionSource: 'DirectLake - lakehouse'")
        lines.append("")
        
        return "\n".join(lines)
