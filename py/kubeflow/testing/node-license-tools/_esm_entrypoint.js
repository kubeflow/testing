#!/usr/bin/env node
/**
 * This is the entrypoint for CLI access to the package
 * It uses esm on runtime to convert ES Module and export as CommonJS
 * 
 *  Read more: https://www.npmjs.com/package/esm
 * 
 * This allows local execution as:
 *     
 *     node .\_esm_entrypoint.js get_license_info
 *
 * Which is needed by package.json when we set this up as a global package
 * 
 */

// Set options as a parameter, environment variable, or rc file.
require = require("esm")(module)
module.exports = require("./node_lic.js")