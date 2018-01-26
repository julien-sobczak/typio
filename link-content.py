#/bin/env python

import os
import json

# Read the dataset to filter on active projects
with open('dataset.json') as f:
    dataset = json.load(f)

# Traverse avaiable projects
for root, dirs, files in os.walk("content/github/"):
    for name in dirs:

        # Search the directory into the dataset
        for p in dataset:
            if not p['origin'] == 'github':
                continue
            if "active" in p and not p['active']:
                continue
            
            organization, project = p['url'].replace('https://github.com/', '').split('/')
            commit = p['commit']
            slug = organization + '_' + project + '_' + commit
            print(slug)

            if slug == name:
                print('Project', slug, 'is active')
                
                # Create symlink
                cwd = os.getcwd()
                src = os.path.join(cwd, 'content/github/' + slug)
                dest = os.path.join(cwd, 'build/es6-bundled/content/github/' + slug) 
                os.symlink(src, dest)
                break
            
    # Do not recurse over subfolders
    break
  
