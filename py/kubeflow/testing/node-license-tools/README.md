# CLI tools to fetch go library's license info
**This tool is based on the implementation written [here](../go-license-tools).** This tool is written as a single-entrypoint CLI, much like `kubectl` or `git` with commands and options as the primary driver for interaction (rather than seperate scripts).

## General Usage
This library will build the CSV file that can be consumed by [go-license-tools/concatenate_license.py](../go-license-tools/concatenate_license.py)

## How to get all dependencies with license and source code?

### Setup
Download this folder to your local folder namely `<license_tool>` and install it:
```bash
$ npm i -g </path/to/license_tool>
```

### Running (with installation)
```bash
$ node_lic -h   # For help
$ node_lic get_license_info </path/to/repository_to_scan>
```

### Running (without installation)
```bash
$ cd </path/to/license_tool>
$ npm start -- get_license_info </path/to/repository_to_scan>
```

### Finally
Now that you have `license_info.csv` you can follow the instructions on how to use `concatenate-license` from [go-license-tools](../go-license-tools/README.md).
