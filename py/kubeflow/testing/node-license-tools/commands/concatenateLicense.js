/**
 * Command implementation for concatenate license for node_lic
 * About:
 * - Reads a license.csv file to fetch all dependencies
 * - Fetch licenses from URLs and concat into final file
 * - All this data is then written into argv.output
 */
import {writeFileSync, readFileSync} from 'fs'
import fetch from 'node-fetch'
import {Semaphore} from 'await-semaphore';

// Var declarations
const rateLimiter = new Semaphore(10) // Only allow 10 concurrent requests at any given moment

// Helper functions
const readHttpFile = async route => {
    const release = await rateLimiter.acquire()
    return await fetch(route)
        .then(data => (release(), data.text()))
        .catch(e => {
            throw Error(`[readHTTPFile] Could not fetch file URL [${route}]: ${e.message || e}`)
        })
}


// Command execution promise
const getLicenseInfo = async _ => {
    let data
    try {data = readFileSync(argv.l)}
    catch(e) {
        throw Error(`Failed to open input file because: ${err.message || err}`)
    }

    const repo_failed = []
    const content = []
    const tasks = (data+'').split(/\r?\n/).map(async line => {
        line = line.trim()
        const [repo, licLink, licName, licDownload] = line.split(',')
        try {
            console.error(`Repo ${repo} has license download link ${licDownload}`)
            const licText = await readHttpFile(licDownload)
            content.push(`
                ${'-'.repeat(80)}
                ${repo}  ${licName}  ${licLink}
                ${'-'.repeat(80)}
                ${licText}
            `.split(/\r?\n/).map(i => i.replace(/^(    ){3,4}/, '')).filter(i=>i).join('\n'))
        } catch(e) {
            console.error('[failed]', e)
            repo_failed.push(repo)
        }
    })
    await Promise.all(tasks)
    console.log('Writing to', argv.output)
    try {writeFileSync(argv.output, content.join('\n'))} catch(e) {console.error('Failed to write data to output file', e)}
    if (!repo_failed.length) return
    console.error(`Failed to download license file for ${repo_failed.length} repos.`)
    repo_failed.forEach(repo => console.error(`    ${repo}`))
}

export default getLicenseInfo
