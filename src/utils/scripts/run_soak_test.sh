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
    TESTS=$(xmllint --xpath "string(//testsuite/@tests)" "$ITERATION_DIR/functional-tests.xml" 2>/dev/null || echo "0")
    FAILURES=$(xmllint --xpath "string(//testsuite/@failures)" "$ITERATION_DIR/functional-tests.xml" 2>/dev/null || echo "0")
    ERRORS=$(xmllint --xpath "string(//testsuite/@errors)" "$ITERATION_DIR/functional-tests.xml" 2>/dev/null || echo "0")
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
    TESTS=$(xmllint --xpath "string(//testsuite/@tests)" "build/reports/soak-iteration-$i/functional-tests.xml" 2>/dev/null || echo "0")
    FAILURES=$(xmllint --xpath "string(//testsuite/@failures)" "build/reports/soak-iteration-$i/functional-tests.xml" 2>/dev/null || echo "0")
    ERRORS=$(xmllint --xpath "string(//testsuite/@errors)" "build/reports/soak-iteration-$i/functional-tests.xml" 2>/dev/null || echo "0")
    PASSED=$((TESTS - FAILURES - ERRORS))
    TIME=$(xmllint --xpath "string(//testsuite/@time)" "build/reports/soak-iteration-$i/functional-tests.xml" 2>/dev/null || echo "0")
    
    echo "$PASSED passed, $FAILURES failed, $ERRORS errors in ${TIME}s"
    
    if [ $FAILURES -gt 0 ] || [ $ERRORS -gt 0 ]; then
      echo ""
      echo "Failed tests:"
      xmllint --xpath "//testcase[@*[local-name()='failure' or local-name()='error']]/@name" "build/reports/soak-iteration-$i/functional-tests.xml" 2>/dev/null | grep -o 'name="[^"]*"' | cut -d'"' -f2 | sed 's/^/  - /' || echo "  (Could not parse test names)"
    fi
  else
    echo "No test results found"
  fi
done
echo "======================================"

[ $FAILED_COUNT -eq 0 ] || exit 1
