Set vars for a list of ws
```
python main.py -h 192.168.71.225.nip.io -o organisation -w workspace_name -c set_workspace_var -l test_data/set_vars.csv
```

Find ws info
```
python main.py -h 192.168.71.225.nip.io -o organisation -c find_workspace -w workspace_id
python main.py -h 192.168.71.225.nip.io -o organisation -c find_workspace -w workspace_name
python main.py -h 192.168.71.225.nip.io -o organisation -c find_workspace -l workspaces_list
```

List Ws
```
python main.py -h 192.168.71.225.nip.io -o organisation -c list_workspaces
```