import shutil
import tempfile
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import ir
import run_graph
from test_shared_parallel import fixture


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix='graph-package-'))
        self.cpath, self.plan = fixture(self.temp/'original')
        self.ppath = self.cpath.parent/'plan.json'
        ir.write(self.ppath, self.plan)

    def tearDown(self): shutil.rmtree(self.temp)

    def test_packaged_graph_keeps_exact_input_binding(self):
        copied, plan = run_graph.package(self.cpath, self.ppath, self.temp/'run')
        self.assertEqual(ir.digest(copied), ir.digest(self.cpath))
        self.assertEqual(ir.validate(copied, plan)[2], ['T001','T002'])
        self.assertEqual(ir.local_packet(copied, plan, 'T002'), ir.local_packet(self.cpath, self.plan, 'T002'))

    def test_packaging_rejects_source_path_escape(self):
        shutil.copyfile(self.cpath.parent/'source.json', self.temp/'source.json')
        c = ir.load(self.cpath)
        c['source']['path'] = '../source.json'
        ir.write(self.cpath, c)
        self.plan['contract_sha256'] = ir.digest(self.cpath)
        ir.write(self.ppath, self.plan)
        with self.assertRaisesRegex(ir.Invalid, 'stage the source'):
            run_graph.package(self.cpath, self.ppath, self.temp/'run')


if __name__ == '__main__': unittest.main()
