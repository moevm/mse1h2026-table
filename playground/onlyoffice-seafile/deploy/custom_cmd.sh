#!/bin/bash

(
  while [ ! -f /shared/seafile/conf/seahub_settings.py ]; do
    sleep 2
  done

  sleep 3

  if ! grep -q "ENABLE_ONLYOFFICE" /shared/seafile/conf/seahub_settings.py; then
    echo "=> Adding OnlyOffice in seahub_settings.py..."
    
    cat <<EOF >> /shared/seafile/conf/seahub_settings.py

# ==========================================
# OnlyOffice Settings (Auto-injected)
# ==========================================
ENABLE_ONLYOFFICE = True
VERIFY_ONLYOFFICE_CERTIFICATE = False
ONLYOFFICE_APIJS_URL = '${SEAFILE_SERVER_PROTOCOL:-http}://${SEAFILE_SERVER_HOSTNAME}/onlyofficeds/web-apps/apps/api/documents/api.js'
ONLYOFFICE_FILE_EXTENSION = ('doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'odt', 'fodt', 'odp', 'fodp', 'ods', 'fods')
ONLYOFFICE_EDIT_FILE_EXTENSION = ('docx', 'pptx', 'xlsx')
ONLYOFFICE_FORCE_SAVE = True
ONLYOFFICE_JWT_SECRET = '${ONLYOFFICE_JWT_SECRET}'
EOF
    echo "=> OnlyOffice setup successfull"
  else
    echo "=> OnlyOffice setup exists"
  fi
) &

exec /sbin/my_init -- /scripts/enterpoint.sh
