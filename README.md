# Jenkins Environment Validator

This tool validates Windows Jenkins nodes for:

- Environment variables
- ArcPy license
- SDE read connectivity
- Network share access
- Jenkins agent status
- GitLab PAT access
- Disk space
- Installed tools

## Run locally

python validator.py config.json

## Output

report.json

## Exit Codes

0 = success  
1 = partial failure