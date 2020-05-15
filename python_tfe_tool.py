#!python3

import sys
import json
import getopt
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import os
import pydoc

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
    print('\t-c, --command\t\tCommand name, as for list below.')
    print('\t-w, --workspace\t\tWorkspace name or ID')
    print('\t-x, --filter\t\tFilter output for a certain name or id. Applicable to vars and workspaces')
    print('\t-v, --variable\t\tNew workspace variable <key:value>')
    print('\t-l, --list\t\tPath to file containing CSV (comma separated) data to use for bulk actions')
    print('\t--credentials\t\tPath to custom TFE credentials file.')

    print('\nCommands:')
    print('\tfind_workspaces\t\tList all Terraform workspaces or a specific workspace ID or Name. Optional filter with ID or name')
    print('\tfind_vars\t\tList all or filtered vars in the specified workspace. Requires workspace')
    print('\tset_workspace_var\tSet or updates var for specified workspace(s)\n\t\t\t\tRequire workspace ID or name, key_value or file list')

    print('\nExamples:')
    print('\nList all workspaces:')
    print('\t{0} -o myorg -c find_workspaces '.format(tool_name))
    print('\nFind workspace ID or Name:')
    print('\t{0} -o myorg -c find_workspaces -x ws-L9AQYF1RqRRkQs1k'.format(tool_name))
    print('\t{0} -o myorg -c find_workspaces -x my_workspace'.format(tool_name))
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


def find_vars(hostname, token, organization, workspace, var_filter):

    api_url = "https://{0}/api/v2/vars?filter%5Borganization%5D%5Bname%5D={1}&filter%5Bworkspace%5D%5Bname%5D={2}".format(hostname, organization, workspace)

    headers = {'Content-Type': 'application/vnd.api+json',
               'Authorization': 'Bearer {0}'.format(token)}

    r = requests.get(api_url, headers=headers, verify=False)

    if r.status_code == 200:
        all_vars = json.loads(r.content.decode('utf-8'))

        for var in all_vars["data"]:
            if var_filter is "":
                return var["id"], var["attributes"]["key"], var["attributes"]["value"]
            else:
                if var["id"] == var_filter or var["attributes"]["key"] == var_filter:
                    return var["id"], var["attributes"]["key"], var["attributes"]["value"]

        print("No vars found with selected criterias/filter")
        return None
    elif r.status_code == 404 and r.reason == "Not Found":
        workspace_name = find_workspaces(hostname, token, organization, workspace)
        find_vars(hostname, token, organization, workspace_name, var_filter)
    else:
        print("{0}, {1}".format(r.status_code, r.reason))
        return None


def find_workspaces(hostname, token, organization, workspace_filter):

    api_url = "https://{0}/api/v2/organizations/{1}/workspaces".format(hostname, organization)

    headers = {'Content-Type': 'application/vnd.api+json',
               'Authorization': 'Bearer {0}'.format(token)}

    r = requests.get(api_url, headers=headers, verify=False)

    if r.status_code == 200:
        all_workspaces = json.loads(r.content.decode('utf-8'))

        if workspace_filter is "":
            for item in all_workspaces["data"]:
                print(item["id"], " ", item["attributes"]["name"])
            return None

        else:
            for item in all_workspaces["data"]:
                if item["id"] == workspace_filter:
                    return item["attributes"]["name"]

                if item["attributes"]["name"] == workspace_filter:
                    return item["id"]

        print("No workspace info found with selected criterias/filter")
        return None
    else:
        print(r.reason)
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
def set_workspace_var(hostname, token, organization, workspace, key_value):
    key_value = key_value.split(':', 1)

    # Make sure workspace id is valida, else find workspace id
    if find_workspaces(hostname, token, workspace) is None:
        workspace = find_workspaces(hostname, token, organization, workspace)

    api_url = "https://{0}/api/v2/workspaces/{1}/vars".format(hostname, workspace)

    data = {
        "data": {
            "type": "vars",
            "attributes": {
                "key": key_value[0],
                "value": key_value[1],
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
        print("Key {0} already created. Overwriting with value.".format(key_value[0]), key_value[1])
        varid = find_var_id(hostname, token, workspace, key_value[0])

        if varid is not None:
            return update_workspace_var(hostname, token, workspace, key_value, varid)

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
    filter = ""

    try:
        opts, args = getopt.getopt(argv, "c:h:w:v:l:o:x:", ["help", "command=", "hostname=", "workspace=", "variable=",
                                                            "organization=", "credentials=", "list=", "filter="])
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

        elif opt in ("-x", "--filter"):
            filter = arg

        elif opt in "--credentials":
            credentials_file = arg

    api_token = get_terraform_token(credentials_file, hostname)

    if command == "find_workspaces":
        print(find_workspaces(hostname, api_token, organization, filter))

    elif command == "find_vars":
        a, b, c = find_vars(hostname, api_token, organization, workspace, filter)
        if a is not None:
            print("[{0}] {1}: {2}".format(a, b, c))

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
