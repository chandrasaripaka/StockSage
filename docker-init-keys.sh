#!/bin/bash

# Check if the tiger_private_key.pem file already exists
if [ ! -f "tiger_private_key.pem" ]; then
    echo "No Tiger Brokers private key found. Creating a template file..."
    echo "-----BEGIN RSA PRIVATE KEY-----
Please replace this with your actual Tiger Brokers private key.
If you don't have one, you can run with USE_MOCK_TIGER=true to use
the mock client for development purposes.
-----END RSA PRIVATE KEY-----" > tiger_private_key.pem
    echo "Created template private key file. Please replace with your actual key before connecting to Tiger Brokers API."
fi