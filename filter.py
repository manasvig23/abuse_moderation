import re
from typing import Dict, List

def load_abusive(filepath="abusive_words.txt"):
    """Load abusive words from file"""
    try:
        with open(filepath, "r") as f:
            return [line.strip().lower() for line in f.readlines() if line.strip()]
    except FileNotFoundError:
        # Fallback list if file doesn't exist
        return ["stupid", "idiot", "fuck", "hate", "dumb", "shit", "damn", "asshole", "bitch"]

abusive_words = load_abusive()

# Context patterns that might indicate NON-abusive usage
positive_context_patterns = [
    r"fucking (awesome|brilliant|amazing|great|good|cool|nice|perfect|excellent)",
    r"stupid (simple|easy|obvious|clear)",
    r"damn (good|great|awesome|cool|nice|impressive)",
    r"shit (ton|load) of (good|great|awesome|fun)",
    r"badass (in a good way|move|skill|talent)"
]

# Patterns that are clearly abusive (high confidence)
clearly_abusive_patterns = [
    r"you (are|'re) (stupid|idiot|dumb|fucking)",
    r"fuck you",
    r"go to hell", 
    r"kill yourself",
    r"hate you",
    r"piece of (shit|crap)"
]

def analyze_context(text: str) -> Dict[str, any]:
    """
    Analyze context to determine if flagged words might be non-abusive
    This is the AUTO-REVIEW logic
    """
    text_lower = text.lower().strip()
    
    # Check for positive context patterns
    positive_context_score = 0
    for pattern in positive_context_patterns:
        if re.search(pattern, text_lower):
            positive_context_score += 1
    
    # Check for clearly abusive patterns  
    clearly_abusive_score = 0
    for pattern in clearly_abusive_patterns:
        if re.search(pattern, text_lower):
            clearly_abusive_score += 2  # Weight these higher
    
    # Question/statement analysis
    is_question = text.strip().endswith('?')
    has_please = 'please' in text_lower
    has_thanks = any(word in text_lower for word in ['thanks', 'thank you', 'thx'])
    
    # Positive indicators
    politeness_score = sum([is_question and not clearly_abusive_score, has_please, has_thanks])
    
    return {
        "positive_context": positive_context_score,
        "clearly_abusive": clearly_abusive_score,
        "politeness_score": politeness_score,
        "likely_false_positive": positive_context_score > 0 and clearly_abusive_score == 0
    }

def is_abusive_with_auto_review(text: str) -> Dict[str, any]:
    """
    Enhanced abuse detection with AUTO-REVIEW capability
    This determines if system should auto-approve or keep hidden
    """
    if not text or not text.strip():
        return {
            "is_abusive": 0,
            "confidence": 0,
            "flagged_words": [],
            "auto_action": "approve",
            "reason": "empty_text"
        }
    
    text_lower = text.lower().strip()
    
    # Method 1: Exact word matches
    exact_matches = []
    for word in abusive_words:
        # Use word boundaries to avoid false positives
        pattern = r'\b' + re.escape(word) + r'\b'
        if re.search(pattern, text_lower):
            exact_matches.append(word)
    
    # Method 2: Handle repeated characters (stuuuupid -> stupid)
    repeated_chars = []
    for word in abusive_words:
        # Create pattern for repeated characters: stupid -> s+t+u+p+i+d+
        pattern = ''
        for char in word:
            pattern += char + '+'
        pattern = r'\b' + pattern + r'\b'
        
        if re.search(pattern, text_lower) and word not in exact_matches:
            repeated_chars.append(word)
    
    # Method 3: Handle character substitutions and masking (st*pid, f**k, stup1d, $tupid)
    substitution_matches = []
    for word in abusive_words:
        # Create pattern for various masking techniques
        pattern = r'\b'
        for i, char in enumerate(word):
            if char.isalpha():
                # Common substitutions: a->@, i->1, o->0, s->$, e->3
                # PLUS masking: any letter -> *, **, #, etc.
                substitutions = {
                    'a': '[a@4*#]', 'e': '[e3*#]', 'i': '[i1!*#]', 'o': '[o0*#]', 's': '[s$5*#]',
                    'b': '[b6*#]', 'g': '[g9*#]', 'l': '[l1*#]', 't': '[t7*#]',
                    'u': '[u*#]', 'c': '[c*#]', 'k': '[k*#]', 'f': '[f*#]', 
                    'd': '[d*#]', 'm': '[m*#]', 'n': '[n*#]', 'p': '[p*#]'
                }
                pattern += substitutions.get(char, f'[{char}*#]')
            else:
                pattern += char
        pattern += r'\b'
        
        if re.search(pattern, text_lower) and word not in exact_matches and word not in repeated_chars:
            substitution_matches.append(word)
    
    # Method 4: Handle multiple asterisk masking (f***ing, f**k, s**t)
    asterisk_matches = []
    for word in abusive_words:
        if len(word) >= 3:  # Only for words 3+ characters
            # Pattern: first letter + asterisks + last letter
            first_last_pattern = f'{word[0]}\\*+{word[-1]}'
            if re.search(first_last_pattern, text_lower) and word not in exact_matches:
                asterisk_matches.append(word)
            
            # Pattern: first two + asterisks + last letter  
            if len(word) >= 4:
                first_two_pattern = f'{word[0]}{word[1]}\\*+{word[-1]}'
                if re.search(first_two_pattern, text_lower) and word not in exact_matches:
                    asterisk_matches.append(word)
    
    # Method 5: Check for spaced out words (s t u p i d)
    spaced_matches = []
    for word in abusive_words:
        # Create pattern for spaced letters: stupid -> s\s*t\s*u\s*p\s*i\s*d
        spaced_pattern = r'\b' + r'\s*'.join(list(word)) + r'\b'
        if re.search(spaced_pattern, text_lower) and word not in exact_matches:
            spaced_matches.append(word)
    
    # Combine all matches
    all_matches = list(set(exact_matches + repeated_chars + substitution_matches + spaced_matches + asterisk_matches))
    
    # If no abusive words found, approve immediately
    if not all_matches:
        return {
            "is_abusive": 0,
            "confidence": 0,
            "flagged_words": [],
            "auto_action": "approve",
            "reason": "no_abusive_words"
        }
    
    # Analyze context for flagged content
    context_analysis = analyze_context(text)
    
    # AUTO-REVIEW DECISION LOGIC
    if context_analysis["clearly_abusive"] > 0:
        # Definitely abusive - keep hidden
        return {
            "is_abusive": 1,
            "confidence": 0.95,
            "flagged_words": all_matches,
            "auto_action": "keep_hidden",
            "reason": "clearly_abusive_pattern",
            "context_analysis": context_analysis
        }
    
    elif context_analysis["likely_false_positive"]:
        # Positive context detected - auto-approve
        return {
            "is_abusive": 0,  # Override detection
            "confidence": 0.3,  # Low confidence in abuse
            "flagged_words": all_matches,
            "auto_action": "auto_approve",
            "reason": "positive_context_detected",
            "context_analysis": context_analysis
        }
    
    elif len(all_matches) == 1 and context_analysis["politeness_score"] > 0:
        # Polite tone with single flagged word - likely false positive
        return {
            "is_abusive": 0,
            "confidence": 0.4,
            "flagged_words": all_matches,
            "auto_action": "auto_approve", 
            "reason": "polite_tone_detected",
            "context_analysis": context_analysis
        }
    
    else:
        # Uncertain case - need human review
        return {
            "is_abusive": 1,
            "confidence": 0.7,
            "flagged_words": all_matches,
            "auto_action": "human_review_needed",
            "reason": "uncertain_context",
            "context_analysis": context_analysis
        }

# Backward compatibility - keep your old function
def is_abusive(text: str) -> Dict[str, any]:
    """
    Simple abuse detection (for backward compatibility)
    Returns basic format like your original function
    """
    result = is_abusive_with_auto_review(text)
    return {
        "is_abusive": result["is_abusive"],
        "confidence": result["confidence"],
        "flagged_words": result["flagged_words"]
    }

# Test the auto-review system
if __name__ == "__main__":
    test_cases = [
        "This is fucking brilliant!",           # Should auto-approve (positive context)
        "You are fucking stupid",              # Should keep hidden (clearly abusive)  
        "That's stupid simple to understand",  # Should auto-approve (positive context)
        "This stupid process is confusing",    # Uncertain - human review
        "Thanks for the help, much appreciated!", # Should approve (polite)
        "You're such a moron",                 # Should keep hidden (clearly abusive)
        "What a fucking awesome performance!", # Should auto-approve (positive context)
        "This was f***ing brilliant!",        # Should auto-approve (masked + positive)
        "You're such an a**hole",             # Should keep hidden (masked + abusive)
        "F**k this s**t",                     # Should keep hidden (clearly abusive)
        "This is f*cking awesome!",           # Should auto-approve (masked + positive)
        "Shit ton of good content here",      # Should auto-approve (positive context)
        "You stupid b*tch",                   # Should keep hidden (clearly abusive)
    ]
    
    print("Testing Auto-Review System:")
    print("=" * 60)
    
    for text in test_cases:
        result = is_abusive_with_auto_review(text)
        print(f"\nText: '{text}'")
        print(f"Action: {result['auto_action'].upper()}")
        print(f"Reason: {result['reason']}")
        print(f"Confidence: {result['confidence']:.2f}")
        if result['flagged_words']:
            print(f"Flagged words: {result['flagged_words']}")