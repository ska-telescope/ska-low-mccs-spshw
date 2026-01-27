#!/bin/bash
set -e

TOTAL_ITERATIONS=${SOAK_ITERATIONS:-10}
FAILED_ITERATIONS=""

for i in $(seq 1 $TOTAL_ITERATIONS); do
  echo "=== Soak Test Iteration $i/$TOTAL_ITERATIONS ==="
  
  ITERATION_DIR="build/reports/soak-iteration-$i"
  mkdir -p "$ITERATION_DIR"
  
  JUNITXML_REPORT_PATH="$ITERATION_DIR/functional-tests.xml" \
  CUCUMBER_JSON_PATH="$ITERATION_DIR/cucumber.json" \
  JSON_REPORT_PATH="$ITERATION_DIR/report.json" \
  make k8s-test || true
  
  if [ -f "$ITERATION_DIR/functional-tests.xml" ]; then
    read TESTS FAILURES ERRORS <<< $(python3 -c "
import xml.etree.ElementTree as ET
tree = ET.parse('$ITERATION_DIR/functional-tests.xml')
suite = tree.find('.//testsuite')
print(suite.get('tests', '0'), suite.get('failures', '0'), suite.get('errors', '0'))
")
    PASSED=$((TESTS - FAILURES - ERRORS))
    
    if [ $FAILURES -gt 0 ] || [ $ERRORS -gt 0 ]; then
      echo "FAILED: Iteration $i ($PASSED passed, $FAILURES failed, $ERRORS errors)"
      FAILED_ITERATIONS="$FAILED_ITERATIONS $i"
    else
      echo "PASSED: Iteration $i ($TESTS passed)"
    fi
  else
    echo "ERROR: No test results found for iteration $i"
    FAILED_ITERATIONS="$FAILED_ITERATIONS $i"
  fi
  
  echo "Completed iteration $i/$TOTAL_ITERATIONS"
done

FAILED_COUNT=$(echo $FAILED_ITERATIONS | wc -w)
PASSED_COUNT=$((TOTAL_ITERATIONS - FAILED_COUNT))
SUCCESS_RATE=$((PASSED_COUNT * 100 / TOTAL_ITERATIONS))

echo ""
echo "======================================"
echo "Soak Test Summary:"
echo "Total Iterations: $TOTAL_ITERATIONS"
echo "Passed Iterations: $PASSED_COUNT"
echo "Failed Iterations: $FAILED_COUNT"
echo "Success Rate: ${SUCCESS_RATE}%"

if [ $FAILED_COUNT -gt 0 ]; then
  echo ""
  echo "Failed iteration numbers:$FAILED_ITERATIONS"
fi
echo "======================================"
echo ""

echo "======================================"
echo "Test Results by Iteration:"
echo "======================================"
for i in $(seq 1 $TOTAL_ITERATIONS); do
  echo ""
  echo "--- Iteration $i ---"
  if [ -f "build/reports/soak-iteration-$i/functional-tests.xml" ]; then
    read TESTS FAILURES ERRORS TIME <<< $(python3 -c "
import xml.etree.ElementTree as ET
tree = ET.parse('build/reports/soak-iteration-$i/functional-tests.xml')
suite = tree.find('.//testsuite')
print(suite.get('tests', '0'), suite.get('failures', '0'), suite.get('errors', '0'), suite.get('time', '0'))
")
    PASSED=$((TESTS - FAILURES - ERRORS))
    
    echo "$PASSED passed, $FAILURES failed, $ERRORS errors in ${TIME}s"
    
    if [ "$FAILURES" != "0" ] || [ "$ERRORS" != "0" ]; then
      echo ""
      echo "Failed tests:"
      python3 -c "
import xml.etree.ElementTree as ET
tree = ET.parse('build/reports/soak-iteration-$i/functional-tests.xml')
for tc in tree.findall('.//testcase'):
    if tc.find('failure') is not None or tc.find('error') is not None:
        print('  - ' + tc.get('name'))
" || echo "  (Could not parse test names)"
    fi
  else
    echo "No test results found"
  fi
done
echo "======================================"

[ $FAILED_COUNT -eq 0 ] || exit 1
