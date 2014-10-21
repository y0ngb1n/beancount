import datetime
import re
import unittest

from beancount.core.amount import D
from beancount.core.amount import Decimal
from beancount.core import inventory
from beancount.core import position
from beancount.query import query_parser as q
from beancount.query import query_compile as c


class TestCompileExpression(unittest.TestCase):

    def test_expr_invalid(self):
        with self.assertRaises(c.CompilationError):
            c.compile_expression(q.Column('invalid'), c.TargetsContext())

    def test_expr_column(self):
        self.assertEqual(c.FilenameColumn(),
                         c.compile_expression(q.Column('filename'), c.TargetsContext()))

    def test_expr_function(self):
        self.assertEqual(c.Sum([c.ChangeColumn()]),
                         c.compile_expression(q.Function('sum', [q.Column('change')]),
                                              c.TargetsContext()))

    def test_expr_unaryop(self):
        self.assertEqual(c.EvalNot(c.AccountColumn()),
                         c.compile_expression(q.Not(q.Column('account')),
                                              c.TargetsContext()))

    def test_expr_binaryop(self):
        self.assertEqual(c.EvalEqual(c.DateColumn(),
                                     c.EvalConstant(datetime.date(2014, 1, 1))),
                         c.compile_expression(
                             q.Equal(q.Column('date'),
                                     q.Constant(datetime.date(2014, 1, 1))),
                             c.TargetsContext()))

    def test_expr_constant(self):
        self.assertEqual(c.EvalConstant(D(17)),
                         c.compile_expression(q.Constant(D(17)), c.TargetsContext()))


class TestCompileExpressionDataTypes(unittest.TestCase):

    def test_expr_function_arity(self):
        # Compile with the correct number of arguments.
        c.compile_expression(q.Function('sum', [q.Column('number')]),
                             c.TargetsContext())

        # Compile with an incorrect number of arguments.
        with self.assertRaises(c.CompilationError):
            c.compile_expression(q.Function('sum', [q.Column('date'),
                                                    q.Column('account')]),
                                 c.TargetsContext())


class TestCompileAggregateChecks(unittest.TestCase):

    def test_is_aggregrate_derived(self):
        columns, aggregates = c.get_columns_and_aggregates(
            c.EvalAnd(
                c.EvalEqual(c.ChangeColumn(), c.EvalConstant(42)),
                c.EvalOr(
                    c.EvalNot(c.EvalEqual(c.DateColumn(),
                                          c.EvalConstant(datetime.date(2014, 1, 1)))),
                    c.EvalConstant(False))))
        self.assertEqual((2, 0), (len(columns), len(aggregates)))

        columns, aggregates = c.get_columns_and_aggregates(
            c.EvalAnd(
                c.EvalEqual(c.ChangeColumn(), c.EvalConstant(42)),
                c.EvalOr(
                    c.EvalNot(c.EvalEqual(c.DateColumn(),
                                          c.EvalConstant(datetime.date(2014, 1, 1)))),
                    # Aggregation node deep in the tree.
                    c.Sum([c.EvalConstant(1)]))))
        self.assertEqual((2, 1), (len(columns), len(aggregates)))

    def test_get_columns_and_aggregates(self):
        # Simple column.
        columns, aggregates = c.get_columns_and_aggregates(c.ChangeColumn())
        self.assertEqual((1, 0), (len(columns), len(aggregates)))

        # Multiple columns.
        columns, aggregates = c.get_columns_and_aggregates(
            c.EvalAnd(c.ChangeColumn(), c.DateColumn()))
        self.assertEqual((2, 0), (len(columns), len(aggregates)))

        # Simple aggregate.
        columns, aggregates = c.get_columns_and_aggregates(
            c.Sum([c.ChangeColumn()]))
        self.assertEqual((0, 1), (len(columns), len(aggregates)))

        # Multiple agreggates.
        columns, aggregates = c.get_columns_and_aggregates(
            c.EvalAnd(c.First([c.AccountColumn()]), c.Last([c.AccountColumn()])))
        self.assertEqual((0, 2), (len(columns), len(aggregates)))

        # Simple non-aggregate function.
        columns, aggregates = c.get_columns_and_aggregates(
            c.Length([c.AccountColumn()]))
        self.assertEqual((1, 0), (len(columns), len(aggregates)))

        # Mix of column and aggregates (this is used to detect this illegal case).
        columns, aggregates = c.get_columns_and_aggregates(
            c.EvalAnd(c.Length([c.AccountColumn()]), c.Sum([c.ChangeColumn()])))
        self.assertEqual((1, 1), (len(columns), len(aggregates)))


class TestCompileDataTypes(unittest.TestCase):

    def test_compile_EvalConstant(self):
        c_int = c.EvalConstant(17)
        self.assertEqual(int, c_int.dtype)

        c_decimal = c.EvalConstant(D('7364.35'))
        self.assertEqual(Decimal, c_decimal.dtype)

        c_str = c.EvalConstant("Assets:Checking")
        self.assertEqual(str, c_str.dtype)

    def test_compile_EvalNot(self):
        c_not = c.EvalNot(c.EvalConstant(17))
        self.assertEqual(bool, c_not.dtype)

    def test_compile_EvalEqual(self):
        c_equal = c.EvalEqual(c.EvalConstant(17), c.EvalConstant(18))
        self.assertEqual(bool, c_equal.dtype)

    def test_compile_EvalGreater(self):
        c_gt = c.EvalGreater(c.EvalConstant(17), c.EvalConstant(18))
        self.assertEqual(bool, c_gt.dtype)

    def test_compile_EvalGreaterEq(self):
        c_ge = c.EvalGreaterEq(c.EvalConstant(17), c.EvalConstant(18))
        self.assertEqual(bool, c_ge.dtype)

    def test_compile_EvalLess(self):
        c_lt = c.EvalLess(c.EvalConstant(17), c.EvalConstant(18))
        self.assertEqual(bool, c_lt.dtype)

    def test_compile_EvalLessEq(self):
        c_le = c.EvalLessEq(c.EvalConstant(17), c.EvalConstant(18))
        self.assertEqual(bool, c_le.dtype)

    def test_compile_EvalMatch(self):
        with self.assertRaises(c.CompilationError):
            c.EvalMatch(c.EvalConstant('testing'), c.EvalConstant(18))
        c_equal = c.EvalMatch(c.EvalConstant('testing'), c.EvalConstant('test.*'))
        self.assertEqual(bool, c_equal.dtype)

    def test_compile_EvalAnd(self):
        c_and = c.EvalAnd(c.EvalConstant(17), c.EvalConstant(18))
        self.assertEqual(bool, c_and.dtype)

    def test_compile_EvalOr(self):
        c_or = c.EvalOr(c.EvalConstant(17), c.EvalConstant(18))
        self.assertEqual(bool, c_or.dtype)

    def test_compile_EvalLength(self):
        with self.assertRaises(c.CompilationError):
            c.Length([c.EvalConstant(17)])
        c_length = c.Length([c.EvalConstant('testing')])
        self.assertEqual(int, c_length.dtype)

    def test_compile_EvalYear(self):
        with self.assertRaises(c.CompilationError):
            c.Year([c.EvalConstant(17)])
        c_year = c.Year([c.EvalConstant(datetime.date.today())])
        self.assertEqual(int, c_year.dtype)

    def test_compile_EvalMonth(self):
        with self.assertRaises(c.CompilationError):
            c.Month([c.EvalConstant(17)])
        c_month = c.Month([c.EvalConstant(datetime.date.today())])
        self.assertEqual(int, c_month.dtype)

    def test_compile_EvalDay(self):
        with self.assertRaises(c.CompilationError):
            c.Day([c.EvalConstant(17)])
        c_day = c.Day([c.EvalConstant(datetime.date.today())])
        self.assertEqual(int, c_day.dtype)

    def test_compile_EvalUnits(self):
        with self.assertRaises(c.CompilationError):
            c.Units([c.EvalConstant(17)])
        c_units = c.Units([c.EvalConstant(inventory.Inventory())])
        self.assertEqual(inventory.Inventory, c_units.dtype)
        c_units = c.Units([c.EvalConstant(position.Position.from_string('100 USD'))])
        self.assertEqual(inventory.Inventory, c_units.dtype)

    def test_compile_EvalCost(self):
        with self.assertRaises(c.CompilationError):
            c.Cost([c.EvalConstant(17)])
        c_cost = c.Cost([c.EvalConstant(inventory.Inventory())])
        self.assertEqual(inventory.Inventory, c_cost.dtype)
        c_cost = c.Cost([c.EvalConstant(position.Position.from_string('100 USD'))])
        self.assertEqual(inventory.Inventory, c_cost.dtype)

    def test_compile_EvalSum(self):
        with self.assertRaises(c.CompilationError):
            c.Sum([c.EvalConstant('testing')])
        c_sum = c.Sum([c.EvalConstant(17)])
        self.assertEqual(int, c_sum.dtype)
        c_sum = c.Sum([c.EvalConstant(D('17.'))])
        self.assertEqual(Decimal, c_sum.dtype)

    def test_compile_EvalCount(self):
        c_count = c.Count([c.EvalConstant(17)])
        self.assertEqual(int, c_count.dtype)

    def test_compile_EvalFirst(self):
        c_first = c.First([c.EvalConstant(17.)])
        self.assertEqual(float, c_first.dtype)

    def test_compile_EvalLast(self):
        c_last = c.Last([c.EvalConstant(17.)])
        self.assertEqual(float, c_last.dtype)

    def test_compile_columns(self):
        class_types = [
            # Postings accessors.
            (c.TypeColumn, str),
            (c.FilenameColumn, str),
            (c.LineNoColumn, int),
            (c.DateColumn, datetime.date),
            (c.FlagColumn, str),
            (c.PayeeColumn, str),
            (c.NarrationColumn, str),
            (c.TagsColumn, set),
            (c.LinksColumn, set),
            (c.AccountColumn, str),
            (c.NumberColumn, Decimal),
            (c.CurrencyColumn, str),
            (c.ChangeColumn, position.Position),
            # Entries accessors.
            (c.TypeEntryColumn, str),
            (c.FilenameEntryColumn, str),
            (c.LineNoEntryColumn, int),
            (c.DateEntryColumn, datetime.date),
            (c.FlagEntryColumn, str),
            (c.PayeeEntryColumn, str),
            (c.NarrationEntryColumn, str),
            (c.TagsEntryColumn, set),
            (c.LinksEntryColumn, set),
            ]
        for cls, dtype in class_types:
            instance = cls()
            self.assertEqual(dtype, instance.dtype)


class TestCompileMisc(unittest.TestCase):

    def test_find_unique_names(self):
        self.assertEqual('date', c.find_unique_name('date', {}))
        self.assertEqual('date', c.find_unique_name('date', {'account', 'number'}))
        self.assertEqual('date_1', c.find_unique_name('date', {'date', 'number'}))
        self.assertEqual('date_2', c.find_unique_name('date', {'date', 'date_1', 'date_3'}))


class CompileSelectBase(unittest.TestCase):

    maxDiff = 8192

    def setUp(self):
        self.parser = q.Parser()

    def compile(self, query):
        """Parse one query and compile it.

        Args:
          query: An SQL query to be parsed.
        Returns:
          The AST.
        """
        statement = self.parser.parse(query.strip())
        return c.compile_select(statement)

    def assertCompile(self, expected, query, debug=False):
        """Assert parsed and compiled contents from 'query' is 'expected'.

        Args:
          expected: An expected AST to compare against the parsed value.
          query: An SQL query to be parsed.
          debug: A boolean, if true, print extra debugging information on the console.
        Raises:
          AssertionError: If the actual AST does not match the expected one.
        """
        actual = self.compile(query)
        if debug:
            print()
            print()
            print(actual)
            print()
        try:
            self.assertEqual(expected, actual)
            return actual
        except AssertionError:
            raise


class TestCompileSelect(CompileSelectBase):

    def test_compile_from(self):
        # Test the compilation of from.
        query = self.compile("SELECT account;")
        self.assertEqual(None, query.c_from)

        query = self.compile("SELECT account FROM CLOSE;")
        self.assertEqual(q.From(None, True), query.c_from)

        query = self.compile("SELECT account FROM length(payee) != 0;")
        self.assertTrue(isinstance(query.c_from, q.From))
        self.assertTrue(isinstance(query.c_from.expression, c.EvalNode))

        with self.assertRaises(c.CompilationError):
            query = self.compile("SELECT account FROM sum(payee) != 0;")

    def test_compile_targets_wildcard(self):
        # Test the wildcard expandion.
        query = self.compile("SELECT *;")
        self.assertTrue(list, type(query.c_targets))
        self.assertGreater(len(query.c_targets), 3)
        self.assertTrue(all(isinstance(target.expression, c.EvalColumn)
                            for target in query.c_targets))

    def test_compile_targets_named(self):
        # Test the wildcard expandion.
        query = self.compile("SELECT length(account), account as a, date;")
        self.assertEqual(
            [q.Target(c.Length([c.AccountColumn()]), 'length_account'),
             q.Target(c.AccountColumn(), 'a'),
             q.Target(c.DateColumn(), 'date')],
            query.c_targets)

    def test_compile_mixed_aggregates(self):
        # Check mixed aggregates and non-aggregates in a target.
        with self.assertRaises(c.CompilationError) as assertion:
            self.compile("""
              SELECT length(account) and sum(length(account));
            """)
        self.assertTrue(re.search('Mixed aggregates and non-aggregates',
                                  str(assertion.exception)))

    def test_compile_aggregates_of_aggregates(self):
        # Check mixed aggregates and non-aggregates in a target.
        with self.assertRaises(c.CompilationError) as assertion:
            self.compile("""
              SELECT sum(sum(length(account)));
            """)
        self.assertTrue(re.search('Aggregates of aggregates',
                                  str(assertion.exception)))

    def test_compile_having(self):
        with self.assertRaises(c.CompilationError):
            self.compile("""
              SELECT account, sum(number) GROUP BY account HAVING sum(number) > 0;
            """)


class TestCompileSelectGroupBy(CompileSelectBase):

    def test_compile_group_by_non_aggregates(self):
        self.compile("""
          SELECT payee GROUP BY payee, length(account);
        """)

        with self.assertRaises(c.CompilationError) as assertion:
            self.compile("""
              SELECT payee GROUP BY payee, last(account);
            """)
        self.assertTrue(re.search('may not be aggregates',
                                  str(assertion.exception)))

    def test_compile_group_by_reference_by_name(self):
        # Valid references to target names.
        self.compile("""
          SELECT payee, last(account) GROUP BY payee;
        """)
        self.compile("""
          SELECT payee as a, last(account) as len GROUP BY a;
        """)

        # References to non-targets have to be valid.
        self.compile("""
          SELECT payee, last(account) as len GROUP BY payee, date;
        """)

        with self.assertRaises(c.CompilationError):
            self.compile("""
              SELECT payee, last(account) as len GROUP BY something;
            """)

    def test_compile_group_by_reference_by_number(self):
        self.compile("""
          SELECT date, payee, narration GROUP BY 1, 2;
        """)

        with self.assertRaises(c.CompilationError):
            self.compile("""
              SELECT date, payee, narration GROUP BY 4;
            """)

    def test_compile_group_by_reference_an_aggregate(self):
        # By name.
        with self.assertRaises(c.CompilationError):
            self.compile("""
              SELECT payee, last(account) as last GROUP BY last;
            """)
        with self.assertRaises(c.CompilationError):
            self.compile("""
              SELECT account, sum(number) as sum_num GROUP BY account, sum_num;
            """)

        # By number.
        with self.assertRaises(c.CompilationError):
            self.compile("""
              SELECT payee, last(account) as last GROUP BY 2;
            """)

        # Explicit aggregate in group-by clause.
        with self.assertRaises(c.CompilationError):
            self.compile("""
              SELECT account, sum(number) GROUP BY account, sum(number);
            """)

    def test_compile_group_by_implicit(self):
        with self.assertRaises(c.CompilationError):
            self.compile("""
              SELECT payee, last(account);
            """)

        self.compile("""
          SELECT first(account), last(account);
        """)

    def test_compile_group_by_coverage(self):
        # Non-aggregates.
        self.compile("SELECT account, length(account);")

        # Aggregates only.
        self.compile("SELECT first(account), last(account);")

        # Mixed with non-aggregates in group-by clause.
        self.compile("SELECT account, sum(number) GROUP BY account;")

        # Mixed with non-aggregates in group-by clause with non-aggregates a
        # strict subset of the group-by columns. 'account' is a subset of
        # {'account', 'flag'}.
        self.compile("""
          SELECT account, sum(number) GROUP BY account, flag;
        """)

        # Non-aggregates not covered by group-by clause.
        with self.assertRaises(c.CompilationError):
            self.compile("""
              SELECT account, date, sum(number) GROUP BY account;
            """)
        with self.assertRaises(c.CompilationError):
            self.compile("""
              SELECT payee, last(account) as len GROUP BY date;
            """)


class TestCompileSelectOrderBy(CompileSelectBase):

    def test_compile_order_by_simple(self):
        self.compile("""
          SELECT account, sum(number) GROUP BY account ORDER BY account;
        """)

    def test_compile_order_by_simple(self):
        self.compile("""
          SELECT account, length(narration) GROUP BY account ORDER BY 1;
        """)

        self.compile("""
          SELECT account, length(narration) as l GROUP BY account ORDER BY l;
        """)

        self.compile("""
          SELECT account, length(narration) GROUP BY account ORDER BY year(date);
        """)

        self.compile("""
          SELECT account GROUP BY account ORDER BY year(date);
        """)

    def test_compile_order_by_aggregate(self):
        self.compile("""
          SELECT account, first(narration) GROUP BY account ORDER BY 2;
        """)

        self.compile("""
          SELECT account, first(narration) as f GROUP BY account ORDER BY f;
        """)

        self.compile("""
          SELECT account, first(narration) GROUP BY account ORDER BY sum(number);
        """)

        self.compile("""
          SELECT account GROUP BY account ORDER BY sum(number);
        """)
