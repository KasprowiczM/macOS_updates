"""Catalog UI selections stay bound to canonical products and sources."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib/python'))
import setup_catalog

class CatalogSelectionBridgeTests(unittest.TestCase):
    def test_exact_selected_pairs_reach_existing_plan_builder(self):
        recipes = {'recipes':[{'product_id':'alpha', 'edition':'gui', 'sources':[{'source_id':'homebrew'}]},
                              {'product_id':'beta', 'edition':'gui', 'sources':[{'source_id':'vendor'}]}]}
        with patch('install_plan.build_install_plan', return_value={'plan':'fixture'}) as build:
            result = setup_catalog.prepare_catalog_selections([('alpha','homebrew')], {}, recipes, 'now')
        self.assertEqual(result, {'plan':'fixture'})
        self.assertEqual(build.call_args.args[0], [dict(product_id='alpha', edition='gui', source_id='homebrew', architecture='arm64')])

    def test_unknown_or_duplicate_selection_is_rejected(self):
        recipes = {'recipes':[{'product_id':'alpha', 'edition':'gui', 'sources':[{'source_id':'homebrew'}]}]}
        for selection in ([('alpha','vendor')], [('missing','homebrew')], [('alpha','homebrew'),('alpha','homebrew')]):
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                setup_catalog.prepare_catalog_selections(selection, {}, recipes, 'now')

if __name__ == '__main__': unittest.main()
