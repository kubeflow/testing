local params = import "../../components/params.libsonnet";
params + {
  components +: {
    "nfs-external" +: {
      nfsServer: "10.128.0.3",
    },
  },
}
