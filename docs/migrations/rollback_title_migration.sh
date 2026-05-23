#!/bin/bash
# Rollback script for title column migration
# Created: 2025-09-23 14:07

BACKUP_FILE="app.db.backup_20250923_140735"
CURRENT_DB="app.db"

echo "🔄 Rolling back database changes..."
echo "📅 Backup file: $BACKUP_FILE"

# Check if backup exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Error: Backup file $BACKUP_FILE not found!"
    echo "Available backups:"
    ls -la *.backup_*
    exit 1
fi

# Create a backup of current state before rollback
echo "📦 Creating backup of current state..."
cp "$CURRENT_DB" "${CURRENT_DB}.pre_rollback_$(date +%Y%m%d_%H%M%S)"

# Restore from backup
echo "🔄 Restoring from backup..."
cp "$BACKUP_FILE" "$CURRENT_DB"

echo "✅ Rollback completed successfully!"
echo "📊 Database restored to state from: $(date -r $BACKUP_FILE)"
echo ""
echo "🔍 Verify your data:"
echo "   - Check that your entries are intact"
echo "   - Verify login still works"
echo "   - Confirm no title column exists"
echo ""
echo "⚠️  Remember to restart your Flask server!"