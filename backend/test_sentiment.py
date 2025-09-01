#!/usr/bin/env python3
"""
Test script to verify improved sentiment analysis functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sentiment_analysis import analyze_sentiment, fallback_sentiment_analysis

def test_sentiment_analysis():
    """Test sentiment analysis with various types of news articles"""
    
    test_cases = [
        {
            "company": "Tesla",
            "article": "Tesla has announced a breakthrough in battery technology that could revolutionize electric vehicles. The new battery design increases range by 40% while reducing costs by 30%. This innovation positions Tesla as the clear market leader in EV technology and could significantly boost their competitive advantage in the growing electric vehicle market.",
            "expected_sentiment": "positive"
        },
        {
            "company": "Microsoft",
            "article": "Microsoft faces challenges in the cloud computing market as competitors gain ground. However, the company's strategic investments in AI and machine learning are showing promising results. Their Azure platform continues to grow, and recent partnerships with major enterprises demonstrate strong market positioning.",
            "expected_sentiment": "positive"
        },
        {
            "company": "Apple",
            "article": "Apple's latest iPhone launch was met with mixed reviews. While the new features are innovative, some users report performance issues and battery problems. The company is working to address these concerns through software updates.",
            "expected_sentiment": "neutral_to_positive"
        },
        {
            "company": "Netflix",
            "article": "Netflix is struggling with declining subscriber numbers and increased competition from streaming rivals. The company's recent price increases have led to customer dissatisfaction, and their content strategy is being questioned by investors.",
            "expected_sentiment": "negative"
        }
    ]
    
    print("Testing Improved Sentiment Analysis System")
    print("=" * 50)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i}: {test_case['company']} ---")
        print(f"Expected: {test_case['expected_sentiment']}")
        print(f"Article: {test_case['article'][:100]}...")
        
        try:
            # Test main sentiment analysis
            result = analyze_sentiment(test_case['company'], test_case['article'])
            
            if result:
                print(f"✅ Main Analysis Result:")
                print(f"   Score: {result.get('Score', 'N/A')}")
                print(f"   Sentiment: {result.get('Sentiment', 'N/A')}")
                print(f"   Summary: {result.get('Summary', 'N/A')}")
                if 'Reasoning' in result:
                    print(f"   Reasoning: {result.get('Reasoning', 'N/A')}")
                print(f"   Keywords: {', '.join(result.get('Keywords', []))}")
                
                # Check if sentiment matches expectation
                sentiment = result.get('Sentiment', '').lower()
                expected = test_case['expected_sentiment']
                
                if 'positive' in expected and 'positive' in sentiment:
                    print("   🎯 Sentiment matches expectation!")
                elif 'negative' in expected and 'negative' in sentiment:
                    print("   🎯 Sentiment matches expectation!")
                elif 'neutral' in expected and 'neutral' in sentiment:
                    print("   🎯 Sentiment matches expectation!")
                else:
                    print(f"   ⚠️ Sentiment may not match expectation (got: {sentiment})")
                    
            else:
                print("❌ Main analysis failed, testing fallback...")
                # Test fallback analysis
                fallback_result = fallback_sentiment_analysis(test_case['company'], test_case['article'])
                if fallback_result:
                    print(f"✅ Fallback Analysis Result:")
                    print(f"   Score: {fallback_result.get('Score', 'N/A')}")
                    print(f"   Sentiment: {fallback_result.get('Sentiment', 'N/A')}")
                    print(f"   Summary: {fallback_result.get('Summary', 'N/A')}")
                    print(f"   Reasoning: {fallback_result.get('Reasoning', 'N/A')}")
                    print(f"   Keywords: {', '.join(fallback_result.get('Keywords', []))}")
                else:
                    print("❌ Both main and fallback analysis failed")
                    
        except Exception as e:
            print(f"❌ Error in test case {i}: {e}")
    
    print("\n" + "=" * 50)
    print("Sentiment Analysis Testing Complete!")

if __name__ == "__main__":
    test_sentiment_analysis()
