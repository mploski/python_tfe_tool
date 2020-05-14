#!python3

import sys
import json
import getopt
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import os

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def usage(tool_name):

    # Find script name
    tool_name = tool_name.split("/")[-1]

    print('usage: test.py -o <organization> -c <command> [args]\n')
    print('This scripts facilitates working around certain feature of Terraform Cloud\n'
          'or Enterprise and can be used to run bulk actions over multiple entities.')
    print('\nArguments:')
    print('\t--help\t\t\tShow this help message and exit')
    print('\t-h, --hostname\t\tTerraform Enterprise hostname. By default, it uses "app.terraform.io"')
    print('\t-o, --organisation\tOrganization')
    print('\t-w, --workspace\t\tWorkspace name or ID')
    print('\t-v, --variable\t\tNew workspace variable <key:value>')
    print('\t-l, --list\t\tPath to file containing CSV (comma separated) data to use for bulk actions')
    print('\t-c, --command\t\tCommand name, as for list below.')
    print('\t--credentials\t\tPath to custom TFE credentials file.')
    print('\nCommands:')
    print('\tlist_workspaces\t\tList all Terraform workspaces.')
    print('\tfind_workspace\t\tFinds either workspace name or ID.\n\t\t\t\tRequire workspace ID, name or file list.')
    print('\tset_workspace_var\tSet or updates var for specified workspace(s)\n\t\t\t\tRequire workspace ID or name, key_value or file list')
    print('\nExamples:')
    print('\nFind workspace ID or Name:')
    print('\t{0} -o myorg -c find_workspace -w ws-L9AQYF1RqRRkQs1k'.format(tool_name))
    print('\t{0} -o myorg -c find_workspace -w my_workspace'.format(tool_name))
    print('\nList all available workspaces:')
    print('\t{0} -o myorg -c list_workspaces'.format(tool_name))
    print('\nSet or update workspaces vars:')
    print('\t{0} -o myorg -c set_workspace_var -w my_workspace -v "foo:bar"'.format(tool_name))
    print('\t{0} -o myorg -c set_workspace_var -w my_workspace -l test_data/set_vars.csv'.format(tool_name))


# Retrieve auth token from Terraform cloud/enterprise credentials file
def get_terraform_token(credentials_file, hostname):
    if credentials_file is "":
        home = os.getenv("HOME")
        with open(home+'/.terraform.d/credentials.tfrc.json') as f:
            file_content = f.read()

        return json.loads(file_content)["credentials"][hostname]["token"]
    else:
        with open(credentials_file) as f:
            file_content = f.read()

        return json.loads(file_content)["credentials"][hostname]["token"]


def list_workspaces(hostname, token, organization):

    api_url = "https://{0}/api/v2/organizations/{1}/workspaces".format(hostname, organization)

    headers = {'Content-Type': 'application/vnd.api+json',
               'Authorization': 'Bearer {0}'.format(token)}

    r = requests.get(api_url, headers=headers, verify=False)

    if r.status_code == 200:
        return json.loads(r.content.decode('utf-8'))
    else:
        return None


# Find either workspace name or ID
# - checks if the passed value is an ID or a Name
# - calls find_workspace_id if passed value is a name
# - calls find_workspace_name if passed value is a id
def find_workspace(hostname, token, organization, workspace, file_list=""):

    if file_list is "":
        if workspace is not "":
            r = find_workspace_id(hostname, token, organization, workspace)

            if r is not None:
                print(r)
            else:
                r = find_workspace_name(hostname, token, workspace)
                if r is not None:
                    print(r)
                else:
                    print("Workspace {0} not found.".format(workspace))
        else:
            print("I need a workspace name or id.")

    else:
        with open(file_list) as l:
            line = l.readline()
            while line:
                workspace = line.strip().split(",", 1)[0]
                find_workspace(hostname, token, organization, workspace)
                line = l.readline()


# Finds ID of the passed Workspace name
def find_workspace_id(hostname, token, organization, workspace):

    api_url = "https://{0}/api/v2/organizations/{1}/workspaces/{2}".format(hostname, organization, workspace)

    headers = {'Content-Type': 'application/vnd.api+json',
               'Authorization': 'Bearer {0}'.format(token)}
    r = requests.get(api_url, headers=headers, verify=False)

    if r.status_code == 200:
        return json.loads(r.content.decode('utf-8'))["data"]["id"]
    else:
        return None


# Finds Name of the passed Workspace ID
def find_workspace_name(hostname, token, workspace):

    api_url = "https://{0}/api/v2/workspaces/{1}".format(hostname, workspace)

    headers = {'Content-Type': 'application/vnd.api+json',
               'Authorization': 'Bearer {0}'.format(token)}
    r = requests.get(api_url, headers=headers, verify=False)

    if r.status_code == 200:
        return json.loads(r.content.decode('utf-8'))["data"]["attributes"]["name"]
    else:
        return None


# Finds ID of the passed variable name
def find_var_id(hostname, token, workspace, varname):
    api_url = 'https://{0}/api/v2/workspaces/{1}/vars'.format(hostname, workspace)

    headers = {'Content-Type': 'application/vnd.api+json',
               'Authorization': 'Bearer {0}'.format(token)}

    r = requests.get(api_url, headers=headers, verify=False)

    if r.status_code == 200:
        all_vars = json.loads(r.content.decode('utf-8'))

        for var in all_vars["data"]:
            if var["attributes"]["key"] == varname:
                return var["id"]
    else:
        return None

# Update existing workspace var. Requires var id
def update_workspace_var(hostname, token, workspace, keyvalue, varid):

    api_url = "https://{0}/api/v2/workspaces/{1}/vars/{2}".format(hostname, workspace, varid)

    data = {
        "data": {
            "id": varid,
            "attributes": {
                "key": keyvalue[0],
                "value": keyvalue[1],
                "category": "terraform",
                "hcl": False,
                "sensitive": False
            },
            "type": "vars"
        }
    }

    headers = {'Content-Type': 'application/vnd.api+json',
               'Authorization': 'Bearer {0}'.format(token)}

    r = requests.patch(api_url, data=json.dumps(data), headers=headers, verify=False)

    if r.status_code == 200:
        return json.loads(r.content.decode('utf-8'))
    else:
        print(r.content)
        return None


# Creates or updates var in workspace(s)
# If new var, it creates it and set the value
# If existing var, it calls find_var_id() and update_workspace_var() to update its value
def set_workspace_var(hostname, token, organization, workspace, keyvalue):
    keyvalue = keyvalue.split(':', 1)

    # Make sure workspace id is valida, else find workspace id
    if find_workspace_name(hostname, token, workspace) is None:
        workspace = find_workspace_id(hostname, token, organization, workspace)

    api_url = "https://{0}/api/v2/workspaces/{1}/vars".format(hostname, workspace)

    data = {
        "data": {
            "type": "vars",
            "attributes": {
                "key": keyvalue[0],
                "value": keyvalue[1],
                "category": "terraform",
                "hcl": False,
                "sensitive": False
            }
        }
    }

    headers = {'Content-Type': 'application/vnd.api+json',
               'Authorization': 'Bearer {0}'.format(token)}

    r = requests.post(api_url, data=json.dumps(data), headers=headers, verify=False)

    if r.status_code == 200:
        return json.loads(r.content.decode('utf-8'))

    elif r.status_code == 422 and r.json()["errors"][0]["detail"] == "Key has already been taken":
        print("Key {0} already created. Overwriting with value.".format(keyvalue[0]), keyvalue[1])
        varid = find_var_id(hostname, token, workspace, keyvalue[0])

        if varid is not None:
            return update_workspace_var(hostname, token, workspace, keyvalue, varid)

    elif r.status_code == 404:
        return r.status_code


def main(argv):

    hostname = "app.terraform.io"
    organization = ""
    workspace = ""
    key_value = ""
    file_list = ""
    command = ""
    credentials_file = ""

    try:
        opts, args = getopt.getopt(argv, "c:h:w:v:l:o:", ["help", "command=", "hostname=", "workspace=", "variable=",
                                                          "organization=", "credentials=", "list="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    for opt, arg in opts:
        if opt == '--help':
            usage()
            sys.exit()

        elif opt in ("-c", "--command"):
            command = arg

        elif opt in ("-h", "--hostname"):
            hostname = arg

        elif opt in ("-w", "--workspace"):
            workspace = arg

        elif opt in ("-v", "--variable"):
            key_value = arg

        elif opt in ("-o", "--organization"):
            organization = arg
            
        elif opt in ("-l", "--list"):
            file_list = arg

        elif opt in "--credentials":
            credentials_file = arg

    api_token = get_terraform_token(credentials_file, hostname)

    if command == "list_workspaces":
        all_workspaces = list_workspaces(hostname, api_token, organization)

        if all_workspaces is not None:
            for item in all_workspaces["data"]:
                print(item["id"], " ", item["attributes"]["name"])
        else:
            print("No workspaces found.")

    elif command == "find_workspace":
        find_workspace(hostname, api_token, organization, workspace, file_list)

    elif command == "find_workspace_name":
        w = find_workspace_name(hostname, api_token, workspace)
        if w is not None:
            print(w)
        else:
            print("Workspace not found.")

    elif command == "find_workspace_id":
        w = find_workspace_id(hostname, api_token, organization, workspace)
        if w is not None:
            print(w)
        else:
            print("Workspaces not found.")

    elif command == "set_workspace_var":
        if file_list is "":
            print("Setting var {0} in workspace {1}".format(key_value, workspace))
            set_workspace_var(hostname, api_token, organization, workspace, key_value)

        else:
            with open(file_list) as l:
                line = l.readline()
                while line:
                    entry = line.strip().split(",")
                    if len(entry) <= 2:
                        print("Required fields for change not found in file entry: \n{0}".format(entry))

                    elif len(entry) >= 3:
                        set_workspace_var(hostname, api_token, organization, entry[0],
                                          "{0}:{1}".format(entry[1],entry[2]))

                    line = l.readline()

    else:
        usage(sys.argv[0])
        sys.exit(2)


if __name__ == "__main__":
    main(sys.argv[1:])
