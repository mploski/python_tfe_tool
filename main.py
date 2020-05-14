#!/usr/bin/python3

import sys
import json
import getopt
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import os

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def get_terraform_token(c, h):
    if c is "":
        home = os.getenv("HOME")
        with open(home+'/.terraform.d/credentials.tfrc.json') as f:
            file_content = f.read()

        return json.loads(file_content)["credentials"][h]["token"]
    else:
        with open(c) as f:
            file_content = f.read()

        return json.loads(file_content)["credentials"][h]["token"]


def list_workspaces(h, t, o):

    api_url = "https://{0}/api/v2/organizations/{1}/workspaces".format(h, o)

    headers = {'Content-Type': 'application/vnd.api+json',
               'Authorization': 'Bearer {0}'.format(t)}

    response = requests.get(api_url, headers=headers, verify=False)

    if response.status_code == 200:
        return json.loads(response.content.decode('utf-8'))
    else:
        return None


def find_workspace(h, t, o, w, file_list=""):

    if file_list is "":
        if w is not "":
            r = find_workspace_id(h, t, o, w)

            if r is not None:
                print(r)
            else:
                r = find_workspace_name(h, t, w)
                if r is not None:
                    print(r)
                else:
                    print("Workspace {0} not found.".format(w))
        else:
            print("I need a workspace name or id.")

    else:
        with open(file_list) as l:
            line = l.readline()
            while line:
                w = line.strip().split(",", 1)[0]
                find_workspace(h, t, o, w)
                line = l.readline()


def find_workspace_id(h, t, o, w):

    api_url = "https://{0}/api/v2/organizations/{1}/workspaces/{2}".format(h, o, w)

    headers = {'Content-Type': 'application/vnd.api+json',
               'Authorization': 'Bearer {0}'.format(t)}
    response = requests.get(api_url, headers=headers, verify=False)

    if response.status_code == 200:
        return json.loads(response.content.decode('utf-8'))["data"]["id"]
    else:
        return None


def find_workspace_name(h, t, w):

    api_url = "https://{0}/api/v2/workspaces/{1}".format(h, w)

    headers = {'Content-Type': 'application/vnd.api+json',
               'Authorization': 'Bearer {0}'.format(t)}
    response = requests.get(api_url, headers=headers, verify=False)

    if response.status_code == 200:
        return json.loads(response.content.decode('utf-8'))["data"]["attributes"]["name"]
    else:
        return None


def find_var_id(h, t, w, v):
    api_url = 'https://{0}/api/v2/workspaces/{1}/vars'.format(h, w)

    headers = {'Content-Type': 'application/vnd.api+json',
               'Authorization': 'Bearer {0}'.format(t)}

    response = requests.get(api_url, headers=headers, verify=False)

    if response.status_code == 200:
        all_vars = json.loads(response.content.decode('utf-8'))

        for var in all_vars["data"]:
            if var["attributes"]["key"] == v:
                return var["id"]
    else:
        return None


def update_workspace_var(h, t, w, kv, var_id):

    api_url = "https://{0}/api/v2/workspaces/{1}/vars/{2}".format(h, w, var_id)

    data = {
        "data": {
            "id": var_id,
            "attributes": {
                "key": kv[0],
                "value": kv[1],
                "category": "terraform",
                "hcl": False,
                "sensitive": False
            },
            "type": "vars"
        }
    }

    headers = {'Content-Type': 'application/vnd.api+json',
               'Authorization': 'Bearer {0}'.format(t)}

    response = requests.patch(api_url, data=json.dumps(data), headers=headers, verify=False)

    if response.status_code == 200:
        return json.loads(response.content.decode('utf-8'))
    else:
        print(response.content)
        return None


def set_workspace_var(h, t, o, w, kv):
    key_value = kv.split(':', 1)

    # Make sure workspace id is valida, else find workspace id
    if find_workspace_name(h, t, w) is None:
        w = find_workspace_id(h, t, o, w)

    api_url = "https://"+h+"/api/v2/workspaces/"+w+"/vars"

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
               'Authorization': 'Bearer {0}'.format(t)}

    response = requests.post(api_url, data=json.dumps(data), headers=headers, verify=False)

    if response.status_code == 200:
        return json.loads(response.content.decode('utf-8'))

    elif response.status_code == 422 and response.json()["errors"][0]["detail"] == "Key has already been taken":
        print("Key {0} already created. Overwriting with value.".format(key_value[0]), key_value[1])
        var_id = find_var_id(h, t, w, key_value[0])

        if var_id is not None:
            return update_workspace_var(h, t, w, key_value, var_id)

    elif response.status_code == 404:
        return response.status_code


def main(argv):

    hostname = "app.terraform.io"
    organization = ""
    workspace = ""
    variable = ""
    file_list = ""
    command = ""
    credentials_file = ""

    try:
        opts, args = getopt.getopt(argv, "c:h:w:v:l:o:", ["help", "command=", "hostname=", "workspace=", "variable=",
                                                          "organization=", "credentials=", "list="])

    except getopt.GetoptError:
        print('Usage:')
        print('test.py -h <hostname> -o <organization> -w <workspace> -v <key:value>')
        print('\nAlternative with list:')
        print('test.py -h <hostname> -o <organization> -l <filename>')
        sys.exit(2)

    for opt, arg in opts:
        if opt == '--help':
            print('Usage:')
            print('test.py -h <hostname> -o <organization> -w <workspace> -c <command> -v <key:value>')
            print('\nAlternative with file:')
            print('test.py -h <hostname> -o <organization> -c <command> -l <filename>')
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
        print("Enter a valid command.")


if __name__ == "__main__":
    main(sys.argv[1:])
