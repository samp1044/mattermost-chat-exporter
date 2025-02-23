import requests
import json
import argparse
import sys
import os
import datetime
import shutil
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
parser.add_argument("--hide-token", help="do not print the session token when logging-in as user/password", action='store_true')

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

if user == None and token == None:
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
    
    if args.hide_token != True:
        print("Logged in as " + str(user) + " with token " + str(token))
        
else:
    headers["Authorization"] = "Bearer " + token


# Get current user
current_user_url = api_url + "/users/me"
response = requests.get(current_user_url, headers=headers)
fail_if_not_ok(response, "Retrieving user failed")
current_user = response.json()
user_id = current_user["id"]

print("User " + str(user) + " was found with id " + str(user_id))

# Setup output directory
export_path = Path(output, "Mattermost-Export-" + datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
export_path.mkdir(parents=True)

# -------------------------------------------
#  Export users
# -------------------------------------------

# Export all users
users_url = api_url + "/users"
response = requests.get(users_url, headers=headers)
fail_if_not_ok(response, "Retrieving all users failed")

all_users = response.json()

users_export_path = Path(export_path, "users")
users_export_path.mkdir(parents=True)

with (users_export_path / "users.json").open("w", encoding="utf8") as f:
    json.dump(all_users, f)

with (users_export_path / "me.json").open("w", encoding="utf8") as f:
    json.dump(current_user, f)

## Add profile pictures and export user data

users_picture_export_path = Path(users_export_path, "profile-pictures")
users_picture_export_path.mkdir(parents=True)

for user in all_users:
    profile_pic_url = api_url + "/users/" + user["id"] + "/image"
    response = requests.get(profile_pic_url, headers=headers, stream=True)
    
    if response.status_code == 404 or response.status_code == 403:
        resonse = requests.get(profile_pic_url + "/default", headers=headers, stream=True)
        
    fail_if_not_ok(response, "Failed to retrieve profile picture for user " + user["email"])

    with (users_picture_export_path / user["id"]).open("wb") as f:
        for chunk in response.iter_content(1024):
            f.write(chunk)

# -------------------------------------------
#  Export custom emoji
# -------------------------------------------

emojis_export_path = Path(export_path, "emojis")
emojis_export_path.mkdir(parents=True)

emojis_images_export_path = emojis_export_path / "images"
emojis_images_export_path.mkdir(parents=True)

emoji_page = 0
emoji_url = api_url + "/emoji"

while True:
    params = {"per_page":200, "page": emoji_page}

    response = requests.get(emoji_url, headers=headers, params=params)
    fail_if_not_ok(response, "Retrieving custom emoji list page " + str(emoji_page) + "failed")

    emojis = response.json()

    if len(emojis) <= 0:
        break

    emoji_page += 1

    with (emojis_export_path / "emojis.json").open("a+", encoding="utf8") as f:
        json.dump(emojis, f)

    # Retrieve custom emoji images
    for emoji in emojis:
        emoji_image_url = emoji_url + "/" + emoji["id"] + "/image"
        response = requests.get(emoji_image_url, headers=headers, stream=True)
            
        fail_if_not_ok(response, "Failed to retrieve image for emoji " + str(emoji["id"]))

        with (emojis_images_export_path / emoji["id"]).open("wb") as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)


# -------------------------------------------
#  Export teams
# -------------------------------------------

teams_url = api_url + "/users/me/teams"
response = requests.get(teams_url, headers=headers)
fail_if_not_ok(response, "Retrieving teams failed")

teams = response.json()

teams_export_path = Path(export_path, "teams")
teams_export_path.mkdir(parents=True)

with (teams_export_path / "teams.json").open("w", encoding="utf8") as f:
    json.dump(teams, f)

# -------------------------------------------
#  Export channels per team
# -------------------------------------------

for team in teams:
    team_export_path = teams_export_path / team["id"]
    team_export_path.mkdir(parents=True)

    # Download icon
    teams_icon_url = api_url + "/teams/" + team["id"] + "/image"
    response = requests.get(teams_icon_url, headers=headers, stream=True)

    if response.status_code != 404:
        fail_if_not_ok(response, "Failed to retrieve team icon for team " + team["name"])

        with (team_export_path / "icon").open("wb") as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)

    # Get channel per team for current user
    channels_url = api_url + "/users/me/teams/" + team["id"] + "/channels"
    response = requests.get(channels_url, headers=headers)
    
    fail_if_not_ok(response, "Failed to retrieve channels for team " + team["name"])

    channels = response.json()

    # Export channel definitions
    with (team_export_path / "channels.json").open("w", encoding="utf8") as f:
        json.dump(channels, f)

    # Export each channel
    for channel in channels:
        channel_export_path = team_export_path / channel["id"]
        channel_export_path.mkdir(parents=True)

        # Export members
        members_url = api_url + "/channels/" + channel["id"] + "/members"
        response = requests.get(members_url, headers=headers)
        
        fail_if_not_ok(response, "Failed to retrieve members for channel " + channel["name"])

        members = response.json()
        with (channel_export_path / "members.json").open("w", encoding="utf8") as f:
            json.dump(members, f)

        # Export pinned posts
        pinned_posts_url = api_url + "/channels/" + channel["id"] + "/pinned"
        response = requests.get(pinned_posts_url, headers=headers)
        
        fail_if_not_ok(response, "Failed to retrieve pinned posts for channel " + channel["name"])

        pinned_posts = response.json()
        with (channel_export_path / "pinned-posts.json").open("w", encoding="utf8") as f:
            json.dump(pinned_posts, f)

        # Export all posts
        page = 0

        attachment_path = channel_export_path / "attachments"
        attachment_path.mkdir(parents=True)

        thumbnails_path = channel_export_path / "thumbnails"
        thumbnails_path.mkdir(parents=True)

        while True:
            posts_url = api_url + "/channels/" + channel["id"] + "/posts"
            params = {"per_page":200, "page": page}

            response = requests.get(posts_url, headers=headers, params=params)
            fail_if_not_ok(response, "Failed to retrieve posts for page " + str(page) + " for channel " + channel["name"])

            posts = response.json()
            posts_list = posts["posts"].values()

            if len(posts_list) <= 0:
                break
            
            with (channel_export_path / ("posts-page-" + str(page) + ".json")).open("w", encoding="utf8") as f:
                json.dump(posts, f)

            page += 1

            # Export all attachments
            file_ids = [p["file_ids"] for p in posts_list if "file_ids" in p]
            file_ids = [id for file_id_list in file_ids for id in file_id_list]

            for file_id in file_ids:
                # File
                file_url = api_url + "/files/" + file_id
                response = requests.get(file_url, headers=headers, stream=True)

                fail_if_not_ok(response, "Failed to retrieve file " + file_id)
                
                with (attachment_path / file_id).open("wb") as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)

                # Thumbnail
                file_url = api_url + "/files/" + file_id + "/thumbnail"
                response = requests.get(file_url, headers=headers, stream=True)
                
                if response.status_code == 400:
                    continue # File has no thumbnail

                fail_if_not_ok(response, "Failed to retrieve thumbnail for file " + file_id)
                
                with (thumbnails_path / file_id).open("wb") as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)