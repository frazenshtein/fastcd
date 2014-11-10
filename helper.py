import os
import re
import sys
import json

def getUserHomeDir():
    return os.path.realpath(os.environ["HOME"])

def replaceHomeWithTilde(path, home):
    if path.startswith(home):
        path = path.replace(home, "~")
    return path

def convertJson(data):
    if isinstance(data, dict):
        return {convertJson(key): convertJson(value) for key, value in data.iteritems()}
    elif isinstance(data, list):
        return [convertJson(element) for element in data]
    elif isinstance(data, unicode):
        string = data.encode("utf-8")
        # if string.isdigit():
        #     return int(string)
        return string
    else:
        return data

def loadJson(filename):
    with open(filename) as file:
        data = file.read()
    # Remove comments
    data = re.sub(r"\/\*.*?\*\/", "", data, flags=re.MULTILINE|re.DOTALL)
    jsonData = json.loads(data)
    return convertJson(jsonData)

def loadConfig(toolName):
    modulePath = os.path.dirname(os.path.realpath(__file__))
    configPath = os.path.join(modulePath, "config.json")
    json = loadJson(configPath)
    config = json[toolName]
    config.update(json["common"])
    return config
