#!/bin/bash
set -e
doctl auth init
doctl apps create --spec infrastructure/digitalocean/app_spec.yaml
echo "Deployed. Check dashboard for live URL."
