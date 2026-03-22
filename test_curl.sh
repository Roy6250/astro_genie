#!/bin/bash

# Curl test script for Astro Genie (mock mode)
# Run with: bash test_curl.sh

BASE_URL="http://localhost:8000"
PHONE="9876543210"

echo "=== Astro Genie - Curl Test Script ==="
echo "Testing with mock WhatsApp (no provider integration)"
echo ""

echo "1️⃣ Health check"
curl -s $BASE_URL/webhook | jq
echo ""

echo "2️⃣ Send greeting"
curl -s -X POST $BASE_URL/webhook \
  -H "Content-Type: application/json" \
  -d "{\"phone\": \"$PHONE\", \"message\": \"Hi\"}" | jq
echo ""

echo "3️⃣ Send DOB"
curl -s -X POST $BASE_URL/webhook \
  -H "Content-Type: application/json" \
  -d "{\"phone\": \"$PHONE\", \"message\": \"15-03-1995\"}" | jq
echo ""

echo "4️⃣ Send TOB (time of birth)"
curl -s -X POST $BASE_URL/webhook \
  -H "Content-Type: application/json" \
  -d "{\"phone\": \"$PHONE\", \"message\": \"10:30\"}" | jq
echo ""

echo "5️⃣ Send POB (place of birth)"
curl -s -X POST $BASE_URL/webhook \
  -H "Content-Type: application/json" \
  -d "{\"phone\": \"$PHONE\", \"message\": \"Mumbai, India\"}" | jq
echo ""

echo "6️⃣ Send name"
curl -s -X POST $BASE_URL/webhook \
  -H "Content-Type: application/json" \
  -d "{\"phone\": \"$PHONE\", \"message\": \"Test User\"}" | jq
echo ""

echo "✅ Test complete! Check app logs for message flow."
echo ""
echo "Alternative: Use /simulate-message endpoint"
echo "curl -X POST $BASE_URL/simulate-message -H 'Content-Type: application/json' -d '{\"phone\": \"$PHONE\", \"message\": \"hello\"}'"
