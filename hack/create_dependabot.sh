#!/bin/bash

yq eval --null-input '.version = 2 | .updates = []' > .github/dependabot.yml

for directory in $(dirname $(find . -type f -name "*ockerfile*") | sort -u); do
    if [[ ${directory} != *"node_modules"* ]]; then
        if ! [[ "$(dirname $(find ./* -type f -name "OWNERS") | sort -u)[@]" == ${directory} ]]; then
            assignees=$(yq eval -j -I=0 '.approvers' ./OWNERS)
            yq eval -i ".updates += {\"package-ecosystem\":\"docker\",\"directory\":\"${directory}\",\"schedule\":{\"interval\":\"daily\"},\"open-pull-requests-limit\":10,\"assignees\":${assignees}}" .github/dependabot.yml
        else
            for owners in $(find ./* -type f -name "OWNERS" | sort -u); do
                if [[ ${directory} == "$(dirname ${owners})" ]]; then
                    assignees=$(yq eval -j -I=0 '.approvers' ${owners})
                    yq eval -i ".updates += {\"package-ecosystem\":\"docker\",\"directory\":\"${directory}\",\"schedule\":{\"interval\":\"daily\"},\"open-pull-requests-limit\":10,\"assignees\":${assignees}}" .github/dependabot.yml
                fi
            done
        fi
    fi
done

for directory in $(dirname $(find . -type f -name "package*.json" -not -path "./*node_modules*") | sort -u); do
    if ! [[ "$(dirname $(find ./* -type f -name "OWNERS") | sort -u)[@]" == ${directory} ]]; then
        assignees=$(yq eval -j -I=0 '.approvers' ./OWNERS)
        yq eval -i ".updates += {\"package-ecosystem\":\"npm\",\"directory\":\"${directory}\",\"schedule\":{\"interval\":\"daily\"},\"open-pull-requests-limit\":10,\"assignees\":${assignees}}" .github/dependabot.yml
    else
        for owners in $(find ./* -type f -name "OWNERS" | sort -u); do
            if [[ ${directory} == "$(dirname ${owners})" ]]; then
                assignees=$(yq eval -j -I=0 '.approvers' ${owners})
                yq eval -i ".updates += {\"package-ecosystem\":\"npm\",\"directory\":\"${directory}\",\"schedule\":{\"interval\":\"daily\"},\"open-pull-requests-limit\":10,\"assignees\":${assignees}}" .github/dependabot.yml
            fi
        done
    fi
done

for directory in $(dirname $(find . -type f -name "*requirements.txt" -not -path "./*node_modules*") | sort -u); do
    if ! [[ "$(dirname $(find ./* -type f -name "OWNERS") | sort -u)[@]" == ${directory} ]]; then
        assignees=$(yq eval -j -I=0 '.approvers' ./OWNERS)
        yq eval -i ".updates += {\"package-ecosystem\":\"pip\",\"directory\":\"${directory}\",\"schedule\":{\"interval\":\"daily\"},\"open-pull-requests-limit\":10,\"assignees\":${assignees}}" .github/dependabot.yml
    else
        for owners in $(find ./* -type f -name "OWNERS" | sort -u); do
            if [[ ${directory} == "$(dirname ${owners})" ]]; then
                assignees=$(yq eval -j -I=0 '.approvers' ${owners})
                yq eval -i ".updates += {\"package-ecosystem\":\"pip\",\"directory\":\"${directory}\",\"schedule\":{\"interval\":\"daily\"},\"open-pull-requests-limit\":10,\"assignees\":${assignees}}" .github/dependabot.yml
            fi
        done
    fi
done

for directory in $(dirname $(find . -type f -name "go.*" -not -path "./*node_modules*") | sort -u); do
    if ! [[ "$(dirname $(find ./* -type f -name "OWNERS") | sort -u)[@]" == ${directory} ]]; then
        assignees=$(yq eval -j -I=0 '.approvers' ./OWNERS)
        yq eval -i ".updates += {\"package-ecosystem\":\"gomod\",\"directory\":\"${directory}\",\"schedule\":{\"interval\":\"daily\"},\"open-pull-requests-limit\":10,\"assignees\":${assignees}}" .github/dependabot.yml
    else
        for owners in $(find ./* -type f -name "OWNERS" | sort -u); do
            if [[ ${directory} == "$(dirname ${owners})" ]]; then
                assignees=$(yq eval -j -I=0 '.approvers' ${owners})
                yq eval -i ".updates += {\"package-ecosystem\":\"gomod\",\"directory\":\"${directory}\",\"schedule\":{\"interval\":\"daily\"},\"open-pull-requests-limit\":10,\"assignees\":${assignees}}" .github/dependabot.yml
            fi
        done
    fi
done

yq eval -i '... style="" | .updates[].directory style="double" | .updates[].package-ecosystem style="double" | .updates[].schedule.interval style="double"' .github/dependabot.yml
