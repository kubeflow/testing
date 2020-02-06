/**
 * Command implementation for get_license_info for node_lic
 * About:
 * - First leverages license-checker to scan local packages for license data
 * - Then converts local paths to github paths (non-deterministically) by 
 *   cross-referencing github using Octocat SDK
 * - All this data is then written into argv.output
 */
import checker from 'license-checker'
import Octokit from '@octokit/rest'
import {readFile, writeFile} from 'fs'
import {retry} from '@octokit/plugin-retry'
import {createTokenAuth} from '@octokit/auth-token'
import {Semaphore} from 'await-semaphore';

// Var declarations
const RetryableOcto = Octokit.plugin(retry)
const rateLimiter = new Semaphore(10) // Only allow 10 concurrent requests at any given moment
let octokit

// Helper functions
const getDefaultBranch = async repoPath => {
    const release = await rateLimiter.acquire()
    try {
        const {data} = await octokit.request(`/repos/${repoPath}`)
        release()
        return data.default_branch
    } catch(e) {
        console.error(`    Failed to read github data for ${repoPath}:`, e.message)
        release()
        throw e
    }
}
const ckNotEmpty = ln => ln

// Main Operations
const readGHToken = _ => new Promise((res, rej) => 
    readFile(argv.gh, (err, data) => 
        err ? rej(`Failed to read github token file: ${err.message}`) : res(data+'')
    )).then(token => {
        // To ignore line endings or whitespace
        const trimmedToken = token.replace(/\s/g, '')
        octokit = new RetryableOcto({auth: trimmedToken, authStrategy: createTokenAuth})
    })

const runScanner = _ => new Promise((res, rej) => {
    console.log('Scanning for packages...')
    checker.init({
        start: argv.input,
    }, (err, packages) => {
        if (err) {
            console.error('    Could not scan for dependencies because:', err)
            return rej(err)
        }
        res(packages) 
    })
})

const formatLicenseData = async packages => {
    console.log('Formatting data...')
    let fails = 0
    const tasks = Object.entries(packages).map(async ([pkg, data], i) => {
        const {
            licenses: licType,
            repository,
            path: baseFolder,
            licenseFile: filePath
        } = data
        if (!repository) {
            fails++
            return console.error('    Could not fetch repository for', pkg, '@', baseFolder)
        }
        if (!filePath) {
            fails++
            return console.error('    Could not fetch license file for', pkg, `(${licType}) @`, baseFolder)
        }
        try {
            const repoPath = repository.replace(/^.+?\.com\/(.+?\/.+?)(\/.*)?$/,'$1')
            const defaultBranch = await getDefaultBranch(repoPath)
            const relLicPath = filePath.slice(baseFolder.length)
                .replace(/\\/g,'/') // For windows
            const baseRepo = ~repository.indexOf('/tree')
                ? repository.replace(/(\/tree\/.+?)\/.+$/, '$1')
                : `${repository}/tree/${defaultBranch}`
            const gitLicPath = `${baseRepo}${relLicPath}`
            const rawLicPath = `https://raw.githubusercontent.com/${repoPath}/${defaultBranch}${relLicPath}`
            return [pkg, gitLicPath, licType, rawLicPath].join(',')
        } catch(e) {
            fails++
            return console.error('    Failed to process data for', pkg, '@', baseFolder)
        }
    })
    return await Promise.all(tasks)
        .then(lines => {
            console.log(`    Finished processing ${lines.length} entries, with ${fails} failures`)
            return lines
        })
}

const writeCSVToFile = lines => new Promise((res, rej) => {
    writeFile(argv.output, lines.filter(ckNotEmpty).join('\n'), err => err ? rej(err) : res())
})

// Command execution promise
const getLicenseInfo = _ => readGHToken()
    .then(runScanner)
    .then(formatLicenseData)
    .then(writeCSVToFile)
    .then(_ => {
        console.log(`Successfully wrote all dependecy data to: ${argv.output}`)
    })

export default getLicenseInfo
