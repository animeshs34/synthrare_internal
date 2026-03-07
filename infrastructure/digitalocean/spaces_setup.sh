#!/bin/bash
set -e
pip install s3cmd
s3cmd --configure
s3cmd mb s3://synthrare-datasets --region nyc3
echo "Spaces bucket ready"
