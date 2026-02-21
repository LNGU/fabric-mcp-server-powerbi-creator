# Test Templates for Fabric MCP Server

This directory contains sample Power BI templates in `.pbip` format for testing Git integration.

## 📁 Contents:

### Sales Dashboard Template

**Location**: `sales-dashboard/`

**Includes:**
- 3 KPI Cards: Total Revenue, Total Profit, Total Units Sold
- Bar Chart: Sales by Region
- Line Chart: Revenue Trend  
- Table: Sales Details

**Sample Data**: `sales-data.csv` (36 records, 6 months, 3 regions, 2 products)

## 🧪 How to Test:

### Option 1: Test with GitHub (Recommended)

1. **Push this folder to GitHub:**
   ```bash
   cd test-templates
   git init
   git add .
   git commit -m "Add sales dashboard template"
   git remote add origin https://github.com/YOUR_ORG/YOUR_REPO.git
   git push -u origin main
   ```

2. **Use your MCP server:**
   ```
   User: "Connect my workspace to the template repository"
   Agent: Calls connect_workspace_to_git()
   
   User: "Deploy the sales dashboard"
   Agent: Calls sync_workspace()
   ```

### Option 2: Test with Azure DevOps

1. Create a new Azure DevOps repository
2. Push these files to the repo
3. Use MCP server to connect and sync

### Option 3: Manual Testing in Power BI Desktop

1. Open Power BI Desktop
2. File → Open
3. Navigate to `sales-dashboard/SalesDashboard.pbip`
4. Import the CSV data when prompted
5. Verify the dashboard displays correctly

## 📊 Expected Result:

After syncing, your Fabric workspace should contain:
- **Sales Dashboard** report with 6 visuals
- Data connected to the CSV file (or your own data source)

## 🔧 Customization:

### To use your own data:
1. Replace `sales-data.csv` with your data (keep column names)
2. Commit changes to Git
3. Call `sync_workspace()` to update

### To modify visuals:
1. Edit `SalesDashboard.Report/report.json`
2. Commit changes
3. Sync workspace

## 📝 Data Schema:

```csv
Date        - Date (YYYY-MM-DD)
Region      - Text (North America, Europe, Asia Pacific)
Product     - Text (Widget A, Widget B)
SalesAmount - Integer (in dollars)
Quantity    - Integer (units sold)
Revenue     - Integer (in dollars)
Profit      - Integer (in dollars)
GrowthRate  - Decimal (0.00 - 1.00)
```

## 🎯 Testing Checklist:

- [ ] Files created with correct structure
- [ ] CSV data is valid
- [ ] `.pbip` file references correct paths
- [ ] `.platform` file has unique `logicalId`
- [ ] Report displays 3 cards + 2 charts + 1 table
- [ ] Git connection succeeds
- [ ] Sync operation completes
- [ ] Report appears in workspace
