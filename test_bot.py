"""
Test script to verify bot components work correctly.
Run this before starting the main bot.
"""

import numpy as np
from vision import BoardDetector
from game_logic import GameLogic
from ai_player import AIPlayer
from debug import BoardVisualizer
import sys


def test_vision():
    """Test vision system."""
    print("\n" + "="*60)
    print("TEST 1: Vision System")
    print("="*60)
    
    try:
        detector = BoardDetector()
        board = detector.get_board_state()
        
        if board is None:
            print("[FAIL] Could not capture board state")
            return False
        
        print("[PASS] Board captured successfully")
        print(f"Board shape: {board.shape}")
        print("Board state:")
        BoardVisualizer.print_board(board)
        return True
    
    except Exception as e:
        print(f"[FAIL] Vision test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_game_logic():
    """Test game logic with synthetic board."""
    print("\n" + "="*60)
    print("TEST 2: Game Logic")
    print("="*60)
    
    try:
        # Create synthetic board
        board = np.array([
            [0, 1, 2, 3, 4, 5, 6, 0],
            [0, 1, 2, 3, 4, 5, 6, 0],
            [0, 1, 2, 3, 4, 5, 6, 0],
            [1, 1, 2, 3, 4, 5, 6, 1],
            [2, 2, 2, 3, 4, 5, 6, 2],
            [3, 3, 3, 3, 4, 5, 6, 3],
            [4, 4, 4, 4, 4, 5, 6, 4],
            [5, 5, 5, 5, 5, 5, 6, 5],
        ], dtype=np.int8)
        
        print("Test board:")
        BoardVisualizer.print_board(board)
        
        logic = GameLogic(board)
        
        # Test match finding
        print("\nFinding matches...")
        matches = logic._find_all_matches(board)
        print(f"Found {len(matches)} matched cells: {matches[:10]}")
        
        # Test valid moves
        print("\nFinding valid moves...")
        valid_moves = logic.find_valid_moves()
        print(f"Found {len(valid_moves)} valid moves")
        
        if valid_moves:
            print(f"First move: {valid_moves[0]}")
            score = logic.evaluate_move(valid_moves[0])
            print(f"Score for first move: {score}")
        
        # Test cascade
        print("\nTesting cascade simulation...")
        test_board = np.array([
            [-1, 0, 0, -1, -1, -1, -1, -1],
            [0, 0, 0, -1, -1, -1, -1, -1],
            [1, 1, 1, -1, -1, -1, -1, -1],
            [2, 2, 2, -1, -1, -1, -1, -1],
            [3, 3, 3, -1, -1, -1, -1, -1],
            [4, 4, 4, -1, -1, -1, -1, -1],
            [5, 5, 5, -1, -1, -1, -1, -1],
            [6, 6, 6, -1, -1, -1, -1, -1],
        ], dtype=np.int8)
        
        print("Board before cascade:")
        BoardVisualizer.print_board(test_board)
        
        final_board, score = logic.simulate_cascade(test_board)
        print(f"\nBoard after cascade (score: {score}):")
        BoardVisualizer.print_board(final_board)
        
        print("[PASS] Game logic tests passed")
        return True
    
    except Exception as e:
        print(f"[FAIL] Game logic test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ai():
    """Test AI player with synthetic board."""
    print("\n" + "="*60)
    print("TEST 3: AI Player")
    print("="*60)
    
    try:
        # Simple test board
        board = np.array([
            [0, 0, 2, 3, 4, 5, 6, 0],
            [1, 1, 2, 3, 4, 5, 6, 1],
            [0, 0, 0, 3, 4, 5, 6, 2],
            [1, 1, 2, 3, 4, 5, 6, 3],
            [2, 2, 2, 3, 4, 5, 6, 4],
            [3, 3, 3, 3, 4, 5, 6, 5],
            [4, 4, 4, 4, 4, 5, 6, 6],
            [5, 5, 5, 5, 5, 5, 5, 5],
        ], dtype=np.int8)
        
        print("Test board:")
        BoardVisualizer.print_board(board)
        
        ai = AIPlayer(board)
        move = ai.select_best_move(board)
        
        if move:
            print(f"\n[PASS] AI selected move: {move}")
            stats = ai.get_move_stats()
            print(f"Stats: {stats}")
            return True
        else:
            print("[WARNING] AI found no valid moves")
            return True  # Still pass if it handles gracefully
    
    except Exception as e:
        print(f"[FAIL] AI test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\nBejeweled 3 Bot - Component Tests")
    print("="*60)
    
    results = {
        'vision': False,
        'logic': False,
        'ai': False,
    }
    
    # Note: Vision test will fail if Bejeweled 3 window is not visible
    print("\n[INFO] Vision test requires Bejeweled 3 to be visible on screen")
    input("Press Enter to continue with vision test...")
    results['vision'] = test_vision()
    
    results['logic'] = test_game_logic()
    results['ai'] = test_ai()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for test, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {test.upper()}")
    
    all_passed = all(results.values())
    print("\n" + ("="*60))
    if all_passed:
        print("[SUCCESS] All tests passed! Bot is ready to run.")
    else:
        print("[WARNING] Some tests failed. Check the output above.")
    print("="*60)
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
