FROM amazon/aws-cli

COPY ./update-iam-assume-role-policy.sh /usr/local/bin/

RUN chmod a+x /usr/local/bin/*.sh

ENTRYPOINT ["/usr/local/bin/update-iam-assume-role-policy.sh"]