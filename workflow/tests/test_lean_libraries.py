"""Independent explicit-library scope, identity and compiler artifact rules."""
import copy
import importlib.util
from pathlib import Path
import unittest

PATH=Path(__file__).resolve().parents[1]/'blocks/lean_library_manifests.py'
SPEC=importlib.util.spec_from_file_location('library_rules_under_test',PATH)
rules=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(rules)
ENV={'lean_version':'0.0.2','mathlib_commit':'a'*40}


def example():
    return {'version':'yui-lean-library-snapshot-1','name':'PublicLib',**ENV,
            'imports':['PublicLib.Entry'],'modules':[{'module':'PublicLib.Entry',
            'source_sha256':'b'*64,'olean_sha256':'c'*64}]}


class LibraryRules(unittest.TestCase):
    def test_explicit_compatible_source_and_native_module(self):
        value=example();self.assertEqual(rules.validate(value,ENV),value)

    def test_other_environment_cannot_reuse_compatible_looking_binary(self):
        for key in ENV:
            value=example();value[key]='0.0.1' if key=='lean_version' else 'd'*40
            with self.subTest(key=key),self.assertRaises(ValueError):rules.validate(value,ENV)

    def test_namespace_shadowing_and_path_escape_are_rejected(self):
        for name in ('Mathlib','Init','Lean','Aesop','Solution','../Escape','PublicLib.Other'):
            value=example();value['name']=name
            value['imports']=[name+'.Entry'];value['modules'][0]['module']=name+'.Entry'
            with self.subTest(name=name),self.assertRaises(ValueError):rules.validate(value,ENV)

    def test_only_explicit_module_entries_are_importable(self):
        for imports in ([],['Other.Entry'],['PublicLib.Entry','PublicLib.Entry']):
            value=example();value['imports']=imports
            with self.subTest(imports=imports),self.assertRaises(ValueError):rules.validate(value,ENV)

    def test_module_paths_duplicates_and_content_identity_are_required(self):
        for change in ({'module':'../PublicLib/Entry'},{'source_sha256':'unbound'},
                       {'olean_sha256':''},{'module':'Other.Entry'}):
            value=example();value['modules'][0].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):rules.validate(value,ENV)
        value=example();value['modules']*=2
        with self.assertRaises(ValueError):rules.validate(value,ENV)

    def test_module_system_companions_are_explicit_and_content_bound(self):
        value=example();value['modules'][0]['companions']={'.olean.private':'d'*64,'.olean.server':'e'*64,'.ir':'f'*64,'.ir.sig':'0'*64}
        self.assertEqual(rules.validate(value,ENV),value)
        for suffix,digest in (('/secret','f'*64),('.olean.server','unbound'),('.lean','f'*64)):
            broken=copy.deepcopy(value);broken['modules'][0]['companions'][suffix]=digest
            with self.subTest(suffix=suffix,digest=digest),self.assertRaises(ValueError):rules.validate(broken,ENV)


if __name__=='__main__':unittest.main()
