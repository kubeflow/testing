"""Script to generate label config yaml file"""
import argparse
import os

import yaml
import requests
import csv

# label_dir = os.path.dirname(os.path.abspath(__file__)) + '/../../label_sync/'

# old label -> new label mapping
label_mapping = {
  # 'approved': 'status/approved',
  'area/os/centos': 'os/centos',
  'area/os/macos': 'os/macos',
  'area/os/ubuntu': 'os/ubuntu',
  'area/os/windows': 'os/windows',
  'area/platform/aws': 'platform/aws',
  'area/platform/azure': 'platform/azure',
  'area/platform/gke': 'platform/gcp',
  'area/platform/minikube': 'platform/minikube',
  'area/release-eng': 'area/build-release',
  'area/releasing': 'area/build-release',
  'area/testing': 'testing',
  'area/ui': 'area/front-end',
  'bug': 'problems/bug',
  'cloud/azure': 'platform/azure',
  'cloud/gke': 'platform/gcp',
  'do-not-merge/work-in-progress': 'status/in progress',
  'enhancement': 'improvement/enhancement',
  'inference': 'area/inference',
  # 'lgtm': 'status/lgtm',
  'question': 'community/question'
}


class LabelColorMapping(object):
  color_mapping_general = {
    'area': 'd2b48c',
    'os': '8cd2b4',
    'addition': 'd28caa',
    'community': 'ecfc15',
    'platform': '2515fc',
    'problems': 'fc2515',
    'priority': {
      'p0': 'db1203',
      'p1': 'db03cc',
      'p2': 'fc9915'
    },
    'status': {
      'approved': '03db12',
      'backlog': 'bc9090',
      'done': 'fca42e',
      'icebox': '808080',
      'in progress': 'ffa500',
      'lgtm': '2efca4'
    },
    'default': '00daff'
  }

  @staticmethod
  def get_color(label):
    color_mapping = LabelColorMapping.color_mapping_general
    names = label.split('/')
    if names[0] not in color_mapping:
      return color_mapping['default']
    if isinstance(color_mapping[names[0]], dict):
      return color_mapping[names[0]][names[1]]
    return color_mapping[names[0]]


# generate label config in yaml
# Two inputs:
#   1. csv file exported from community label definition
#   2. old label -> new label mapping
def csv_to_yml(unparsed_args=None):
  parser = argparse.ArgumentParser(
    description="generate label config")
  parser.add_argument(
    "--output_dir",
    default=os.path.dirname(os.path.abspath(__file__)) + '/../../label_sync/',
    type=str,
    help="Path to input file.")
  args = parser.parse_args(unparsed_args)

  input_csv = os.path.dirname(
    os.path.abspath(__file__)) + "/kubeflow_label_standard.csv"
  output_f = os.path.join(args.output_dir, "kubeflow_label.yml")
  name_to_label = {}
  with open(input_csv, newline='') as raw_csv:
    csv_content = csv.reader(raw_csv, delimiter=',', quotechar='|')
    pref = ''
    label_list = []
    for row in csv_content:
      # words = line.strip(' \t\n\r').split(',')
      if row[0]:
        pref = row[0]
      label_name = ((pref + "/") if pref else '') + row[1]
      label_ins = {
        'name': label_name.lower(),
        'color': LabelColorMapping.get_color(label_name.lower())
      }
      label_list.append(label_ins)
      name_to_label[label_name.lower()] = label_ins
      print("label: " + label_name)
    label_list.sort(key=lambda label_ins: label_ins['name'])
    labels = {"labels": label_list}
  for old_name, new_name in label_mapping.items():
    if new_name in name_to_label:
      if 'previously' not in name_to_label[new_name]:
        name_to_label[new_name]['previously'] = []
      name_to_label[new_name]['previously'].append({'name': old_name.lower()})

  with open(output_f, 'w') as label_yaml:
    yaml.dump(labels, label_yaml, default_flow_style=False)


# helper function to pull current labels from all repos in kubeflow
def get_curr_labels():
  output_f = os.path.dirname(os.path.abspath(__file__)) + '/../../label_sync/' + 'curr_labels.yml'
  repo_labels = []
  for repo in [
      str(repo_info['name']) for repo_info in requests.get(
        'https://api.github.com/orgs/kubeflow/repos').json()
  ]:
    for label in requests.get(
        'https://api.github.com/repos/kubeflow/%s/labels' % repo).json():
      label_name = str(label['name']).lower()
      if label_name not in repo_labels:
        repo_labels.append(label_name)
  repo_labels.sort()
  with open(output_f, 'w') as w_file:
    yaml.dump(repo_labels, w_file, default_flow_style=False)
  for label in repo_labels:
    print("old label: %s," % label)

if __name__ == '__main__':
  # get_curr_labels()
  csv_to_yml()
