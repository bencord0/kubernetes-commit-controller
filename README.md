Kubernetes Commit Controller
----------------------------


Watch a git repository for changes and create a deployment for it


Create a normal Deployment
--------------------------

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment

metadata:
  name: hello
  labels:
    app: web
    component: hello

spec:
  selector:
    matchLabels:
      app: web
      component: hello
  template:
    metadata:
      labels:
        app: web
        component: hello
    spec:
      containers:
      - name: hello
        image: nginx
        ports:
        - containerPort: 80
```

    kubectl apply -f deployment.yaml
    kubectl port-forward deployment/hello 8000:80 &
    curl localhost:8000

Custom Resource Definition
--------------------------

```yaml
# crd.yaml
apiVersion: apiextensions.k8s.io/v1beta1
kind: CustomResourceDefinition

metadata:
  name: dynamicdeployments.condi.me

spec:
  group: condi.me
  version: v1
  scope: Namespaced
  names:
    plural: dynamicdeployments
    singular: dynamicdeployment
    kind: DynamicDeployment
    shortNames:
    - dd
```

    kubectl create -f crd.yaml


Dynamic Deployments
-------------------

```yaml
# dynamicdeployment.yaml
apiVersion: condi.me/v1
kind: DynamicDeployment

metadata:
  name: hello
  labels:
    app: web
    component: hello

spec:
  githubRepository:
    repo: bencord0/hello
    branch: master
  target:
    matchLabels:
      app: web
      component: hello
    container: hello
    containerImageTemplate: bencord0/hello:{commit}

# status:
#   commit: 2e5d3fe1378aac6e3012e61a43d4bdb0376dca97
#   containerImage: bencord0/hello:2e5d3fe1378aac6e3012e61a43d4bdb0376dca97
```

    kubectl create -f dynamicdeployment.yaml
