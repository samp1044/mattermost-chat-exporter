import requests
import json
import argparse
import sys
import os
import datetime
from pathlib import Path

def fail_if_not_ok(response, message):
    if response.status_code != 200:
        print(message + ". Request returned " + str(response.status_code) + ": " + str(response.json()))
        sys.exit(1)

def dir_path(path):
    if os.path.isdir(path):
        return path
    else:
        raise argparse.ArgumentTypeError(f"readable_dir:{path} is not a valid path")

parser = argparse.ArgumentParser()
parser.add_argument("url", help="url of the mattermost instance to export from. E.g. https://my-mattermost.com:1234")
parser.add_argument("-o", "--output", help="export data into this directory", type=dir_path)
parser.add_argument("-t", "--token", help="use this token for authentication and skip log-in call")
parser.add_argument("-u", "--user", help="use this user id for authentication and user specific commands")
parser.add_argument("-p", "--password", help="user this password for authentication")

args = parser.parse_args()

instance = args.url
output = os.getcwd()
token = None
user = None
password = None

if args.output:
    output = args.output

if args.token:
    token = args.token

if args.user:
    user = args.user

if args.password:
    password = args.password

headers =  {"Content-Type":"application/json"}
api_url = instance + "/api/v4"

if user == None:
    user = input("Input user to export data for: ")

if password == None and token == None:
    password = input("Input the password for " + str(user) + ": ")

if token == None:
    login_url = api_url + "/users/login"
    login_dto = {"login_id":user,"password":password}

    response = requests.post(login_url, data=json.dumps(login_dto), headers=headers)
    fail_if_not_ok(response, "Authentication to " + str(instance) + "failed")

    token = response.headers["Token"]
    headers["Authorization"] = "Bearer " + token

    print("Logged in as " + str(user) + " with token " + str(token))
        
else:
    headers["Authorization"] = "Bearer " + token

users_url = api_url + "/users"
response = requests.get(users_url, headers=headers)
fail_if_not_ok(response, "Retrieving all users failed")

users = response.json()
[current_user] = [u for u in users if u['email'] == user]
user_id = current_user["id"]
print("User " + str(user) + " was found with id " + str(user_id))

teams_url = api_url + "/users/" + str(user_id) + "/teams"
response = requests.get(teams_url, headers=headers)
fail_if_not_ok(response, "Retrieving teams for user " + str(user) + "failed")

teams = response.json()
teams_html = "<html><head><title>Mattermost Export - Select Team</title></head><body><h2>Select team</h2><ul>"

for team in teams:
    teams_html += '<li><a href="' + team["id"] + '/index.html">' + team["display_name"] + '</a></li>'

teams_html += "</body></html>"

export_path = Path(output, "Mattermost-Export-" + datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
export_path.mkdir(parents=True)

index_file_path = export_path / "index.html"

with index_file_path.open("w", encoding ="utf-8") as f:
    f.write(teams_html)