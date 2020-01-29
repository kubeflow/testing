#!/usr/bin/env node
/*
 * Copyright 2019 Google LLC
 * 
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 * 
 *     http://www.apache.org/licenses/LICENSE-2.0
 * 
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * 
 */
import yargs from 'yargs'
import getLicenseInfo from './commands/getLicenseInfo.js'
import path from 'path'
import {homedir} from 'os'

const DEFAULT_GH_TOKEN = path.resolve(homedir(), '.github_api_token')
global.argv = yargs
    .command('get_license_info [input-folder]', 'Fetch license information locally and cross-reference with github', {
        output: {
            description: 'Which output file to write to',
            alias: 'o',
            type: 'string',
            default: 'license_info.csv'
        },
        'input-folder': {
            description: 'Input folder to use (uses $cwd, unless overridden)',
            default: '.',
            type: 'string',
            alias: ['i', 'input'],
        },
        'github-api-token-file': {
            description: `You need to create a github personal access token at https://github.com/settings/tokens`+
                `, because github has a very strict limit on anonymous API usage.`,
            default: DEFAULT_GH_TOKEN,
            type: 'string',
            alias: 'gh',
        }
    })
    .help()
    .alias('help', 'h')
    .wrap(yargs.terminalWidth())
    .demandCommand().recommendCommands().strict()
    .scriptName('node_lic').argv

const runCommand = async command => {
    switch(command) {
        case 'get_license_info': return await getLicenseInfo(argv)
    }
    throw `Unimplemented command [${command}] invoked`
}

const [command] = argv._
runCommand(command)
    .catch(e => {
        if (typeof e == 'string') {console.error(e)}
        else {console.error('Error occured:', e)}
        process.exit(1)
    })

