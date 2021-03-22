from boto3.dynamodb.conditions import Attr
from botocore.client import Config
from botocore.exceptions import ClientError
import os
import json
import boto3
import base64
import urllib3
from urllib.error import HTTPError
import http
import inquirer

urllib3.disable_warnings()

# this will prevent long timeouts
BOTO3_CONFIG = Config(connect_timeout=5, retries={"max_attempts": 3})
DYNAMODB_RESOURCE = boto3.resource(
    service_name="dynamodb",
    region_name=os.environ["AWS_REGION"],
    config=BOTO3_CONFIG,
)

SECRET_NAME_TERRAFORM = "terraform"
DYNAMODB_AVMCONFIG_TABLE = "AVMConfig"

### GENERIC FUNCTIONS ###
def aws_get_secret(secret_name: str) -> dict:
    """Retrieve secret by name. No exception handler

    Args:
        secret_name (str): name of the secret to fetch
    Returns:
        dict: secret value
    """
    client = boto3.client(
        service_name="secretsmanager",
        region_name=os.environ["AWS_REGION"],
        config=BOTO3_CONFIG,
    )
    return json.loads(client.get_secret_value(SecretId=secret_name)["SecretString"])


def mask_string(unmasked_value: str, show_chars: int = 4) -> str:
    """Masks value

    Args:
        unmasked_value (str): string to mask
        show_chars (int, optional) : number of chars to show, default 4
    Returns:
        string: masked value, if length less than show_chars only '*' returned
    """
    length = len(unmasked_value)
    if length <= show_chars:
        return "*" * show_chars
    return "*" * (length - show_chars) + unmasked_value[-show_chars:]


def avm_get_config() -> dict:
    """Retrieve avm config based on DYNAMODB_AVMCONFIG_KEYS. No exception handler. DYNAMODB_RESOURCE, DYNAMODB_AVMCONFIG_TABLE,DYNAMODB_AVMCONFIG_KEYS must be set. No exception unhander.

    Returns:
        dict: param->value dictionary
    """
    r = {}
    for item in DYNAMODB_RESOURCE.Table(DYNAMODB_AVMCONFIG_TABLE).scan()["Items"]:
        r[item["parameter"]] = item["value"]
    return r


### TFE CLASS ###
class TFE(object):
    PAGE_SIZE = 100

    def __init__(self, api_url: str, api_token: str):
        """Creates tfe object.
        Args:
            api_url (str): tfe api url
            api_token (str): tfe api token
        """
        self.api_url = api_url
        self.api_token = api_token

    def api_caller(self, method: str, path: str, payload: dict = None):
        """Calls API
        Args:
            method (str): method, ie GET, PUT, POST, PATCH, etc
            path (str): api path
            payloads (optional dict): body of payloads, will be converted to json
        """
        https = urllib3.PoolManager()
        r = https.request(
            method,
            f"{self.api_url}{path}",
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/vnd.api+json",
            },
            body=json.dumps(payload) if payload else None,
        )
        return r

    def workspace_get(self, name: str, organization: str) -> dict:
        """Retrieves tfe workspace data by name. Includes latest run info. Raises exception if not 200. No exception handler.
        Args:
            name (str): workspace name
            organization (str): organization name
        Returns:
            dict: account data
        """
        r = self.api_caller(
            "GET",
            f"/organizations/{organization}/workspaces/{name}?include=current_run",
        )
        if r.status == http.HTTPStatus.OK:
            return json.loads(r.data.decode("UTF-8"))
        elif r.status == http.HTTPStatus.NOT_FOUND:
            return {}
        raise RuntimeError(
            f"status: {r.status}, data: {str(r.data)}"
        )  # this should not happen.

    def team_list(self, organization: str) -> dict:
        """Retrieves team list. Raises exception if response.status!= 200. No exception handler. Pagination handled.
        Args:
            organization (str): organization name
        Returns:
            dict: teams dictionary
        """
        data_aggregated = []
        next_page = 1
        while next_page:
            path = f"/organizations/{organization}/teams?page[size]={self.PAGE_SIZE}&page[number]={next_page}"
            r = self.api_caller("GET", path)
            if r.status != http.HTTPStatus.OK:
                raise HTTPError(
                    self.api_url + path,
                    r.status,
                    r.data.decode("UTF-8"),
                    r.headers,
                    None,
                )
            page_data = json.loads(r.data.decode("UTF-8"))
            data_aggregated.extend(page_data["data"])
            next_page = page_data["meta"]["pagination"].get("next-page")
        page_data[
            "data"
        ] = data_aggregated  # replace last page's data key with aggregated data, leaving the last page's meta and links intact
        return page_data

    def team_get(self, organization: str, team_name: str) -> dict:
        """Get a team data by it's name. No exception handler. Pagination handled.
        Args:
            organization (str): organization name
            team_name (str): team_name to look for
        Returns:
            dict|None: Team id if found. None if not.
        """
        next_page = 1
        while next_page:
            path = f"/organizations/{organization}/teams?page[size]={self.PAGE_SIZE}&page[number]={next_page}"
            r = self.api_caller("GET", path)
            if r.status != http.HTTPStatus.OK:
                raise HTTPError(
                    self.api_url + path,
                    r.status,
                    r.data.decode("UTF-8"),
                    r.headers,
                    None,
                )
            teams = json.loads(r.data.decode("UTF-8"))
            for team in teams["data"]:
                if team["attributes"]["name"] == team_name:
                    return team
            next_page = teams["meta"]["pagination"].get("next-page")
        return None

    def team_workspaces_assign(
        self, access_level: str, workspace_id: str, team_id: str
    ) -> dict:
        """Assign team to workspace with an access level. Raises exception if status != 201. No exception handler.
        Args:
            access_level (str): access level
            workspace_id (str): workspace id
            team_id (str): team id
        Returns:
            dict: result
        """
        payload = {
            "data": {
                "type": "team-workspaces",
                "attributes": {"access": access_level},
                "relationships": {
                    "workspace": {"data": {"type": "workspaces", "id": workspace_id}},
                    "team": {"data": {"type": "teams", "id": team_id}},
                },
            }
        }
        r = self.api_caller("POST", "/team-workspaces", payload)
        if r.status == http.HTTPStatus.CREATED:
            return json.loads(r.data.decode("UTF-8"))
        else:
            raise RuntimeError(f"status: {r.status}, data: {str(r.data)}")

    def team_workspaces_get(self, workspace_id: str) -> dict:
        """List teams assigned to workspace id. Raises exception if status != 200. No exception handler.
        Args:
            workspace_id (str): workspace id
        Returns:
            dict: result
        """
        r = self.api_caller(
            "GET",
            f"/team-workspaces?filter[workspace][id]={workspace_id}",
        )
        if r.status == http.HTTPStatus.OK:
            return json.loads(r.data.decode("UTF-8"))
        elif r.status == http.HTTPStatus.NOT_FOUND:
            return {}
        else:
            raise RuntimeError(f"status: {r.status}, data: {str(r.data)}")

    def teams_create(self, organization: str, team_name: str) -> dict:
        """Assign team to workspace with an access level. Raises exception if status != 201. No exception handler.
        Args:
            organization (str): tfe organization
            team_name (str): team name
        Returns:
            dict: result
        """
        payload = {
            "data": {
                "type": "teams",
                "attributes": {
                    "name": team_name,
                    "organization-access": {
                        "manage-policies": False,
                        "manage-workspaces": False,
                        "manage-vcs-settings": False,
                    },
                },
            }
        }
        r = self.api_caller("POST", f"/organizations/{organization}/teams", payload)
        if r.status == http.HTTPStatus.CREATED:
            return json.loads(r.data.decode("UTF-8"))
        else:
            raise RuntimeError(f"status: {r.status}, data: {str(r.data)}")

    def team_access_update(self, team_workspace_relationship: str, access: str) -> dict:
        """Set team access to workspace. Raises exception if status != 200. No exception handler.
        Args:
            team_workspace_relationship (str): team/workspace relationship
            access_level (str): access level
        Returns:
            dict: result
        """
        payload = {
            "data": {
                "attributes": {
                    "access": access,
                }
            }
        }
        r = self.api_caller(
            "PATCH", f"/team-workspaces/{team_workspace_relationship}", payload
        )
        if r.status == http.HTTPStatus.OK:
            return json.loads(r.data.decode("UTF-8"))
        else:
            raise RuntimeError(f"status: {r.status}, data: {str(r.data)}")


# This will only run when executed locally. Have AWS_PROFILE env variable set and aws config/credentials when running locally
if __name__ == "__main__":
    # you need to export AWS_XRAY_SDK_ENABLED=0 to avoid XRAY fail on local execution
    from optparse import OptionParser
    import uuid
    import logging  # this overrides aws_power_tools for local execution cause json logs are not readable on local execution
    import os
    import time
    import sys

    logger = logging.getLogger()

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "[%(asctime)s %(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)

    terraform_secret = aws_get_secret(SECRET_NAME_TERRAFORM)["terraform"]
    logger.info(
        f"terraform_secret fetched, terraform_secret: {mask_string(terraform_secret)}"
    )

    avm_config = avm_get_config()
    tfe = TFE(avm_config["tfe_api_url"], terraform_secret)
    tfe_org_name = avm_config["tfe_org_name"]
    logger.info(f"tfe_org_name: {tfe_org_name}")

    tfe_workspace_name = input("Enter workspace name: ")
    logger.info(f"tfe_workspace_name: {tfe_workspace_name}")
    tfe_workspace_id = (
        tfe.workspace_get(tfe_workspace_name, tfe_org_name)
        .get("data", {})
        .get("id", {})
    )
    if not tfe_workspace_id:
        logger.error(f"Unable to find tfe_workspace_name: {tfe_workspace_name}")
        exit(1)
    logger.info(f"tfe_workspace_id: {tfe_workspace_id}")

    while True:
        team_name = input("Enter team_to_assign or leave it blank to exit: ")
        if team_name == "":
            logger.info("Exiting...")
            exit(0)
        logger.info(f"team_name: {team_name}")

        logger.info(f"Looking for a team_id with the name: {team_name}")
        team_id = tfe.team_get(tfe_org_name, team_name).get("id", {})
        if not team_name:
            logger.info(f"Unable to find team by name: {team_name}")
            exit(1)
        logger.info(f"team_id: {team_id}")
        questions = [
            inquirer.List(
                "access_level",
                message="Select access level",
                choices=["read", "plan", "write", "admin"],
            ),
        ]
        access_level = inquirer.prompt(questions)["access_level"]
        logger.info(f"access_level: {access_level}")
        tfe.team_workspaces_assign(access_level, tfe_workspace_id, team_id)
        logger.info("Team assigned")
