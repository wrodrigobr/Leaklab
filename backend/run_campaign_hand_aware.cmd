@echo off
cd /d C:\Projetos\leaklab\backend
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
echo ===== CAMPANHA HAND-AWARE (retomada, unbuffered) %date% %time% ===== >> campaign_hand_aware.log
python scripts\precompute_tree_campaign.py >> campaign_hand_aware.log 2>&1
if %errorlevel%==0 (
  echo ===== REANALYZE %date% %time% ===== >> campaign_hand_aware.log
  python scripts\reanalyze_all_labels.py >> campaign_hand_aware.log 2>&1
)
echo ===== FIM %date% %time% ===== >> campaign_hand_aware.log
