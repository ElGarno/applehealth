# Health Auto Export Webhook Setup

This guide explains how to set up automatic daily syncing from the Health Auto Export iOS app to your Synology NAS.

## Architecture

```
iPhone (Health Auto Export App)
    ↓ (HTTP POST when on home WiFi)
Synology NAS (Webhook Container)
    ↓ (Automatic import)
InfluxDB → Grafana
```

## 1. Deploy the Webhook Service

### In Portainer:

1. Update your stack with the new docker-compose.yml
2. Make sure to set these environment variables:
   - `INFLUXDB_URL`: Your InfluxDB URL (e.g., `http://192.168.178.114:8088`)
   - `INFLUXDB_TOKEN`: Your InfluxDB token
   - `INFLUXDB_BUCKET`: Bucket name (default: `apple_health`)
   - `WEBHOOK_SECRET`: (Optional) A secret token for authentication

3. Deploy the stack - only the webhook service will start (import service has a profile)

### Verify the webhook is running:

```bash
curl http://192.168.178.114:8085/health
```

Should return:
```json
{"status": "ok", "service": "health-auto-export-webhook"}
```

## 2. Configure Health Auto Export App

### Install the App
Download "Health Auto Export" from the App Store (by K-Avi).

### Configure REST API Export

1. Open **Health Auto Export**
2. Go to **Settings** → **Export Destinations**
3. Tap **Add Destination** → **REST API**
4. Configure:
   - **Name**: Synology NAS
   - **URL**: `http://192.168.178.114:8085/webhook`
   - **Method**: POST
   - **Headers**: (if using WEBHOOK_SECRET)
     - Key: `Authorization`
     - Value: `Bearer YOUR_SECRET_HERE`

### Configure Automation

1. Go to **Settings** → **Automations**
2. Tap **Add Automation**
3. Configure:
   - **Trigger**: Schedule (e.g., Daily at 23:00)
   - **Condition**: (Optional) WiFi network = your home network name
   - **Action**: Export to "Synology NAS"
   - **Date Range**: Last 2 days (to ensure overlap for incremental import)
   - **Include**:
     - ✅ Health Metrics
     - ✅ Workouts

### Test the Export

1. Go to **Export** tab
2. Select your REST API destination
3. Tap **Export**
4. Check the webhook logs in Portainer

## 3. Security Considerations

### Option A: Use WEBHOOK_SECRET (Recommended)
Set a secret token in docker-compose:
```yaml
environment:
  - WEBHOOK_SECRET=your-secure-random-string
```

Then add the header in Health Auto Export:
- Header: `Authorization`
- Value: `Bearer your-secure-random-string`

### Option B: Firewall Rules
Only allow connections from your local network to port 8085.

### Option C: VPN
Only sync when connected to home VPN.

## 4. Troubleshooting

### Check webhook logs
In Portainer, view the logs of the `apple_health_webhook` container.

### Test webhook manually
```bash
curl -X POST http://192.168.178.114:8085/webhook \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_SECRET" \
  -d '{"data": {"metrics": [], "workouts": []}}'
```

### Verify data directory
The JSON files are saved to `/volume1/docker/apple_health/data/` with the format:
`HealthAutoExport-webhook-YYYYMMDD-HHMMSS.json`

## 5. Running Manual Imports

If you need to run a manual import (e.g., initial data load):

```bash
docker-compose --profile import up apple_health_import
```

Or in Portainer, create a new container from the `apple_health:latest` image with the import command.