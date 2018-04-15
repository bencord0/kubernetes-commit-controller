#!/usr/bin/env python
import os
import logging
import requests
import signal
import threading

from typing import Dict, Iterable, List, Tuple
from kubernetes import client, config

from urllib.parse import quote

# Setup kubernetes clients
config.load_kube_config()
apps = client.AppsV1Api()
crds = client.apis.custom_objects_api.CustomObjectsApi()

stopping = threading.Event()
log = logging.getLogger(__name__)


def stop_running(*args):
    log.error("Stopping controller")
    stopping.set()


def create_label_selector(**kwargs) -> str:
    return ','.join(
        f"{quote(k)}={quote(v)}"
        for k, v in kwargs.items()
    )


def resolve_github_commit(repo: str, branch: str) -> str:
    # Query github api for the tip commit sha
    # Propagate exceptions
    return requests.get(
        f'https://api.github.com/repos/{repo}/git/refs/heads/{branch}',
        headers={'accept': 'application/vnd.github.jean-grey-preview+json'}
    ).json()['object']['sha']


def find_existing_targets(dynamic_deployments: Dict) -> Iterable[Tuple[str, List[Dict]]]:

    for name, dd in dynamic_deployments.items():
        target_container = dd['spec']['target']['container']
        deployment_match_labels = dd['spec']['target']['matchLabels']
        label_selector = create_label_selector(**deployment_match_labels)

        # Enumerate deployments according to the matching labels
        deployments = apps.list_namespaced_deployment(
            namespace="default",
            label_selector=label_selector,
        ).items

        # Multiplpe deployments may match the labels
        # e.g. if the dynamic deployment represents sidecars
        deployments_to_update = []
        for deployment in deployments:
            deployment_names = [d.name for d in deployment.spec.template.spec.containers]
            # Search for deployments that have a named container we want
            if target_container in deployment_names:
                deployments_to_update.append(deployment)

        yield name, deployments_to_update


def get_patch_for_github(dynamic_deployments):
    for name, dd in dynamic_deployments.items():
        spec = dd['spec']
        repo = spec['githubRepository']['repo']
        branch = spec['githubRepository']['branch']
        container_name = spec['target']['container']
        image_template = spec['target']['containerImageTemplate']

        commit = resolve_github_commit(repo, branch)
        yield name, create_deployment_patch(container_name, image_template, commit)


def create_deployment_patch(container_name: str, image_template: str, commit: str) -> Dict:
    return {'spec': {'template': {'spec': {
        'containers': [
            {
                'name': f'{container_name}',
                'image': image_template.format(commit=commit),
            }
        ]
    }}}}


def loop_once():

    # Find dynamic deployments in the default namespace
    # name -> dynamicdeployment definition
    dynamic_deployments: Dict[str, Dict] = {
        dd['metadata']['name']: dd
        for dd in crds.list_namespaced_custom_object(
            group="condi.me",
            version="v1",
            namespace="default",
            plural="dynamicdeployments",
        )['items']
    }

    # Use the selectors to find relavent deployments
    # name -> targets
    targets: Dict[str, List[Dict]] = {
        name: targets
        for name, targets in find_existing_targets(dynamic_deployments)
        if targets  # filter non-existing targets
    }

    # name -> patch
    deployment_patches: Dict[str, Dict] = {
        name: patch
        for name, patch in get_patch_for_github(dynamic_deployments)
    }

    # patch kubernetes deployments
    for name, patch in deployment_patches.items():
        apps.patch_namespaced_deployment(
            namespace='default',
            name=name,
            body=patch,
        )


def main():
    signal.signal(signal.SIGINT, stop_running)
    signal.signal(signal.SIGTERM, stop_running)

    while not stopping.is_set():
        try:
            loop_once()
        except Exception:
            log.exception("Loop failure")

        stopping.wait(59)


if __name__ == "__main__":
    main()
