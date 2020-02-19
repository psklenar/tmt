# coding: utf-8

""" Export metadata into nitrate """

from click import echo, style

import subprocess
import tmt.utils
import nitrate
import pprint
import email
import fmf
import os

log = fmf.utils.Logging('tmt').logger
# Needed for nitrate.Component
DEFAULT_PRODUCT = nitrate.Product(name='RHEL Tests')

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Export
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# TODO debug (echos like when converting)


def export_to_nitrate():
    """ Export fmf metadata to nitrate test cases """
    tree = fmf.Tree('.')
    for fmf_case in list(tree.prune(names=[os.path.abspath('.')[len(tree.root):]])):
        fmf_case_attrs = fmf_case.get()
        case_id = fmf_case_attrs['tcms'][3:]
        nitrate_case = nitrate.TestCase(int(case_id))
        if 'tag' not in fmf_case_attrs:
            fmf_case_attrs['tag'] = list()

        # Components
        try:
            # First remove any components that are already there
            nitrate_case.components.clear()
            # Then add fmf ones
            if fmf_case_attrs['component']:
                comp_list = [nitrate.Component(
                    name=comp, product=DEFAULT_PRODUCT.id) for comp in fmf_case_attrs['component']]
                # TODO exception not existing component
                nitrate_case.components.add(comp_list)
        except KeyError:
            # Defaults to no components
            pass

        # 'tier' attribute into Tier tag
        try:
            fmf_case_attrs['tag'].append("Tier" + str(fmf_case_attrs['tier']))
        except KeyError:
            pass

        # Tags
        nitrate_case.tags.clear()
        # Add special fmf-export tag
        fmf_case_attrs['tag'].append('fmf-export')
        tag_list = [nitrate.Tag(tag) for tag in fmf_case_attrs['tag']]
        nitrate_case.tags.add(tag_list)

        # Default tester
        try:
            email_address = email.utils.parseaddr(fmf_case_attrs['contact'])[1]
            # TODO handle nitrate user not existing and other stuff
            nitrate_case.tester = nitrate.User(email_address)
        except KeyError:
            # Defaults to author of the test case
            pass

        # Duration
        try:
            nitrate_case.time = fmf_case_attrs['duration']
        except KeyError:
            # Defaults to 5 minutes
            nitrate_case.time = '5m'

        # Status
        try:
            if fmf_case_attrs['enabled']:
                nitrate_case.status = nitrate.CaseStatus('CONFIRMED')
            else:
                nitrate_case.status = nitrate.CaseStatus('DISABLED')
        except KeyError:
            # Defaults to enabled
            nitrate_case.status = nitrate.CaseStatus('CONFIRMED')

        # Environment
        try:
            nitrate_case.arguments = ' '.join(
                tmt.utils.dict_to_shell(fmf_case_attrs['environment']))
        except KeyError:
            # FIXME unable to set empty arguments, possibly error in xmlrpc, BZ#1805687
            nitrate_case.arguments = ' '

        struct_field = tmt.utils.StructuredField(nitrate_case.notes)

        # Mapping of fmf case attributes to nitrate sections
        section_to_attr = {'relevancy': 'relevancy', 'description': 'summary',
                           'purpose-file': 'description', 'hardware': 'extra-hardware', 'pepa': 'extra-pepa'}

        for section, attribute in section_to_attr.items():
            try:
                struct_field.set(section, fmf_case_attrs[attribute])
            except KeyError:
                pass

        # fmf identifer
        fmf_id = create_fmf_id(path=os.path.abspath('.'),
                               name=fmf_case.name)[0]

        struct_field.set('fmf', pprint.pformat(fmf_id))

        # Saving case.notes with edited StructField
        nitrate_case.notes = struct_field.save()

        # Update nitrate test case
        nitrate_case.update()

        return 0


# TODO Rewrite
def create_fmf_id(path='.', name=''):
    """
    Create fmf identifier for every case in given directory or specific one

    Returns list of dictionaries with fmf identifiers for each case found in argument path.
    If argument name was specified returns a list with single dictionary with id for given test case.
    """

    origin = subprocess.run(["git", "config", "--get", "remote.origin.url"],
                            capture_output=True).stdout.strip().decode("utf-8")
    url = origin.split('@')[-1]
    ref = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                         capture_output=True).stdout.strip().decode("utf-8")
    tree = fmf.Tree('.')
    path = tree.root
    if name:
        case_names = [name]
    else:
        case_names = [x.name for x in list(tree.prune(
            names=[os.path.abspath('.')[len(tree.root):]]))]

    fmf_ids = list()
    for name in case_names:
        fmf_ids.append({'url': url, 'ref': ref, 'path': path, 'name': name})

    return fmf_ids
