local params = std.extVar("__ksonnet/params").components.prow_pod;
local k = import 'k.libsonnet';

local image = params.image;

// convert a list of two items into a map representing an environment variable
// TODO(jlewi): Should we move this into kubeflow/core/util.libsonnet
local listToMap = function(v)
{
  name: v[0],
  value: v[1],
};

// Function to turn comma separated list of prow environment variables into a dictionary.
local parseEnv= function(v)
	{ 
		local pieces=std.split(v, ","),
		result:: if v != "" && std.length(pieces) > 0 then
		  std.map(
		    function(i) listToMap(std.split(i, "=")),
		    std.split(v, ",")
		  )
		else [],
	}.result;

local namespace = {
  apiVersion: "v1",
  kind: "Namespace",
  metadata: {	
  	name: params.namespace,
  },
};

// TODO(jlewi): Using a replicaset isn't ideal. ks apply doesn't end up causing the
// pods to be restarted.
local pod = {
  apiVersion: "apps/v1beta2",
  kind: "ReplicaSet",
  metadata: {
    name: params.name,
    namespace: params.namespace,
    labels: {
      app: "test-pod",
    },
  },
  spec: {
  	replicas: 1,
  	selector: {
  		matchLabels: {
  			app: "test-pod",
  		},
  	},
  	template: {
  	  metadata: {
  	  	labels: {
  	  		app: "test-pod",
  	  	},
  	  },
	  spec: {
	    containers: [
	      {
	        name: "main",
	        image: image,
	        env: [
	          {

	            name: "PYTHONPATH",
	          	value: "/src/kubeflow/testing/py",
	          },          
	        ] + parseEnv(params.prow_env),
	        // TODO(jlewi): Prow is adding support for init containers and doing the checkout in init containers
	        // so eventually we should be able to stop explicitly calling bootstrap.sh
	        command: [
	          "bash", "-c",
	          "/usr/local/bin/checkout.sh /src " +
	          "&& " +
	          "python " +
	          "-m  " +
	          "kubeflow.testing.run_e2e_workflow " +
	          "--project=mlkube-testing " +
	          "--zone=us-east1-d " +
	          "--cluster=kubeflow-testing " +
	          "--bucket=kubernetes-jenkins " +
	          "--component=" + params.component + " " +
	          "--app_dir=" + params.app_dir + " ",
	        ],
	      },
	    ],	    
	  },  // spec
	  } // template
   }, //spec
};

std.prune(k.core.v1.list.new([namespace, pod]))
