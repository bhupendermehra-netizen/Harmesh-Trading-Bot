#!/data/data/com.termux/files/usr/bin/bash
# Quick alias script — source this or add to ~/.bashrc:
#   source ~/harmesh/scripts/aliases.sh

HARMESH_DIR="$HOME/harmesh"
alias harmesh='cd "$HARMESH_DIR" && bash start.sh'
alias harmesh-paper='cd "$HARMESH_DIR" && source venv/bin/activate && python main.py --mode paper'
alias harmesh-live='cd "$HARMESH_DIR" && source venv/bin/activate && python main.py --mode live'
alias harmesh-status='cd "$HARMESH_DIR" && source venv/bin/activate && python main.py --status'
alias harmesh-upgrade='cd "$HARMESH_DIR" && source venv/bin/activate && python main.py --check-upgrade'
alias harmesh-reset='cd "$HARMESH_DIR" && source venv/bin/activate && python main.py --reset'
alias harmesh-log='tail -f "$HARMESH_DIR/logs/system.log"'
alias harmesh-trades='cat "$HARMESH_DIR/logs/paper_trades.csv" 2>/dev/null | column -t -s"," | head -50'

echo "Harmesh aliases loaded:"
echo "  harmesh         — Interactive menu"
echo "  harmesh-paper   — Phase 1 paper trading"
echo "  harmesh-status  — Dashboard"
echo "  harmesh-upgrade — Check Phase 2 readiness"
echo "  harmesh-log     — Live log tail"
echo "  harmesh-trades  — Recent trades"
