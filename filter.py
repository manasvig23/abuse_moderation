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

positive_context_patterns = [
    r"fucking (awesome|brilliant|amazing|great|good|cool|nice|perfect|excellent)",
    r"damn (good|great|awesome|cool|nice|impressive)",
    r"shit (ton|load) of (good|great|awesome|fun)",
    r"badass (in a good way|move|skill|talent)",
    r"stupid (simple|easy|obvious|clear|question|brilliant|good|but)"
]

clearly_abusive_patterns = [
    r"you (are|'re) (stupid|idiot|dumb|fucking|an asshole|a bitch|shit)",
    r"you (stupid|dumb|fucking) (idiot|moron|bitch|asshole)",
    r"fuck you",
    r"go to hell", 
    r"kill yourself",
    r"hate you",
    r"piece of (shit|crap)",
    r"you asshole",
    r"you (are an|'re an) asshole",
    r"stupid (bitch|asshole|idiot|moron)",
    r"fucking (idiot|moron|stupid|dumb)",
    r"shut up (you )?((stupid|dumb|fucking) )?(bitch|asshole|idiot)",
]

highly_abusive_words = ["asshole", "bitch", "moron", "idiot"]

def analyze_context(text: str) -> Dict[str, any]:
    """Analyze context to determine if flagged words might be non-abusive"""
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
    
    # Check for highly abusive words used in direct address
    highly_abusive_score = 0
    for word in highly_abusive_words:
        
        direct_attack_patterns = [
            rf"\byou (are )?{word}\b",
            rf"\byou're (a |an )?{word}\b", 
            rf"\b{word}$",  
            rf"^{word}\b",  
        ]
        
        for attack_pattern in direct_attack_patterns:
            if re.search(attack_pattern, text_lower):
                highly_abusive_score += 3  
    
    # Question/statement analysis
    is_question = text.strip().endswith('?')
    has_please = 'please' in text_lower
    has_thanks = any(word in text_lower for word in ['thanks', 'thank you', 'thx'])
    
    # Positive indicators
    politeness_score = sum([is_question and not clearly_abusive_score, has_please, has_thanks])
    
    return {
        "positive_context": positive_context_score,
        "clearly_abusive": clearly_abusive_score,
        "highly_abusive": highly_abusive_score,
        "politeness_score": politeness_score,
        "likely_false_positive": positive_context_score > 0 and clearly_abusive_score == 0 and highly_abusive_score == 0
    }

def is_abusive_with_auto_review(text: str) -> Dict[str, any]:
    """This determines if system should auto-approve or keep hidden"""
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
       
    # 1. DEFINITELY ABUSIVE - Auto-hide these cases
    if (context_analysis["clearly_abusive"] > 0 or 
        context_analysis["highly_abusive"] > 0 or
        len(all_matches) >= 3):  # Multiple curse words = likely abusive
        
        return {
            "is_abusive": 1,
            "confidence": 0.95,
            "flagged_words": all_matches,
            "auto_action": "keep_hidden",
            "reason": "clearly_abusive_pattern_or_highly_abusive_words",
            "context_analysis": context_analysis
        }
    
    # 2. POSITIVE CONTEXT - Auto-approve
    elif context_analysis["likely_false_positive"]:
        return {
            "is_abusive": 0,
            "confidence": 0.3,
            "flagged_words": all_matches,
            "auto_action": "auto_approve",
            "reason": "positive_context_detected",
            "context_analysis": context_analysis
        }
    
    # 3. POLITE TONE - Auto-approve
    elif len(all_matches) == 1 and context_analysis["politeness_score"] > 0:
        return {
            "is_abusive": 0,
            "confidence": 0.4,
            "flagged_words": all_matches,
            "auto_action": "auto_approve", 
            "reason": "polite_tone_detected",
            "context_analysis": context_analysis
        }
    
    # 4. SINGLE HIGH-RISK WORD - Auto-hide (NEW RULE)
    elif len(all_matches) == 1 and any(word in highly_abusive_words for word in all_matches):
        return {
            "is_abusive": 1,
            "confidence": 0.8,
            "flagged_words": all_matches,
            "auto_action": "keep_hidden",
            "reason": "high_risk_word_detected",
            "context_analysis": context_analysis
        }
    
    # 5. UNCERTAIN - Human review needed
    else:
        return {
            "is_abusive": 1,
            "confidence": 0.6,
            "flagged_words": all_matches,
            "auto_action": "human_review_needed",
            "reason": "uncertain_context",
            "context_analysis": context_analysis
        }

def is_abusive(text: str) -> Dict[str, any]:
    """Simple abuse detection (for backward compatibility) ; Returns basic format like your original function"""
    result = is_abusive_with_auto_review(text)
    return {
        "is_abusive": result["is_abusive"],
        "confidence": result["confidence"],
        "flagged_words": result["flagged_words"]
    }

# Test the auto-review system
if __name__ == "__main__":
    test_cases = [
        # These should AUTO-HIDE now (no human review needed)
        "You are an asshole",                  
        "You fucking idiot",                   
        "Shut up bitch",                       
        "You stupid moron asshole",            
        
        # These should AUTO-APPROVE (positive context)
        "This is fucking brilliant!",         
        "That's stupid simple to understand", 
        "Thanks for the help, much appreciated!", 
        
        # These should need HUMAN REVIEW (uncertain)
        "This stupid process is confusing",   
        "What a load of shit this is",        
    ]
    
    print("Testing IMPROVED Auto-Review System:")
    print("=" * 70)
    
    for text in test_cases:
        result = is_abusive_with_auto_review(text)
        print(f"\nText: '{text}'")
        print(f"Action: {result['auto_action'].upper()}")
        print(f"Reason: {result['reason']}")
        print(f"Confidence: {result['confidence']:.2f}")
        if result['flagged_words']:
            print(f"Flagged words: {result['flagged_words']}")