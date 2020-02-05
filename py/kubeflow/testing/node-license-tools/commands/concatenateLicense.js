/**
 * Command implementation for get_license_info for node_lic
 * About:
 * - First leverages license-checker to scan local packages for license data
 * - Then converts local paths to github paths (non-deterministically) by 
 *   cross-referencing github using Octocat SDK
 * - All this data is then written into argv.output
 */
import {readFile, writeFileSync} from 'fs'
import fetch from 'node-fetch'
import {Semaphore} from 'await-semaphore';

// Var declarations
const rateLimiter = new Semaphore(10) // Only allow 10 concurrent requests at any given moment

// Helper functions
const readHttpFile = async route => {
    const release = await rateLimiter.acquire()
    return await fetch(route)
        .then(data => (release(), data.text()))
}


// Command execution promise
const getLicenseInfo = async _ => readFile(argv.l, (err, data) => {
    if (err) throw Error(`Failed to open input file because: ${err.message || err}`)

    const repo_failed = []
    const content = []
    ;(data+'').split(/\r?\n/).forEach(async line => {
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
            repo_failed.append(repo)
        }
    })
    try {writeFileSync(argv.o, content.join('\n'))} catch(e) {console.error('Failed to write data to output file', e)}
    if (!repo_failed.length) return
    console.error(`Failed to download license file for ${repo_failed.length} repos.`)
    repo_failed.forEach(repo => console.error(`    ${repo}`))
})

export default getLicenseInfo
