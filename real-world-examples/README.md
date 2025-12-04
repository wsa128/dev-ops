# deployment
Code for VAS deployment

* These are tools for building servers, and app servers
   * infra -- layer over boto3 for talking to AWS
   * server -- library for managing user and superuser linux sessions
   * remote -- command-line-based remote access (for GHA support)
   * ticker -- utility code for generating test log events
   * fixer -- code patching utility

* We also have some test code that is not embedded in the module
   * test-server -- test the server.py server control module

* And some utility code
   * clean-up -- a utility script that -only- deletes instances beginning with "test-"
