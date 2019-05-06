local params = import '../../components/params.libsonnet';

params {
  components+: {
    // Insert component parameter overrides here. Ex:
    // guestbook +: {
    // name: "guestbook-dev",
    // replicas: params.global.replicas,
    // },
    argo+: {
      exposeUi: true,
    },
    "nfs-external"+: {
      nfsServer: '10.10.224.162',
    },
  },
}