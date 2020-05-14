# Terraform Cloud/Enterprise tool helper
This scripts facilitates working around certain feature of Terraform Cloud or Enterprise and can be used to run bulk actions over multiple entities.

usage: `test.py -o <organization> -c <command> [args]`

### Commands
`list_workspaces`         List all Terraform workspaces.

`find_workspace`          Finds either workspace name or ID. Require workspace ID, name or file list.

`set_workspace_var`       Set or updates var for specified workspace(s). Require workspace ID or name, key_value or file list
                                
### Arguments:

`--help`                  Show this help message and exit

`-h, --hostname`          Terraform Enterprise hostname. By default, it uses "app.terraform.io"

`-o, --organisation`      Organization

`-w, --workspace`         Workspace name or ID

`-v, --variable`          New workspace variable <key:value>

`-l, --list`              Path to file containing CSV (comma separated) data to use for bulk actions

`-c, --command`           Command name, as for list below.

`--credentials`           Path to custom TFE credentials file.

### Examples:

**Find workspace ID or Name:**
```
python_tfe_tool.py -o myorg -c find_workspace -w ws-L9AQYF1RqRRkQs1k
python_tfe_tool.py -o myorg -c find_workspace -w my_workspace
```
**List all available workspaces:**

```
python_tfe_tool.py -o myorg -c list_workspaces
```

**Set or update workspaces vars:**
```
python_tfe_tool.py -o myorg -c set_workspace_var -w my_workspace -v "foo:bar"
python_tfe_tool.py -o myorg -c set_workspace_var -w my_workspace -l test_data/set_vars.csv
```