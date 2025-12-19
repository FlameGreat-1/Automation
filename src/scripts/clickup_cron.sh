#!/bin/bash

AUTOMATION_ROOT="/mnt/c/Users/HomePc/Automation"
ENV_FILE="$AUTOMATION_ROOT/.env"
VENV_PATH="$AUTOMATION_ROOT/venv"
PYTHON_SCRIPT="$AUTOMATION_ROOT/src/clickup/Ticket_Fetcher.py"
LOG_DIR="$AUTOMATION_ROOT/logs/cron"
LOCK_FILE="$AUTOMATION_ROOT/logs/clickup_sync.lock"
LOG_FILE="$LOG_DIR/clickup_cron_$(date +%Y%m%d).log"
ERROR_LOG="$LOG_DIR/clickup_errors.log"
PERFORMANCE_LOG="$LOG_DIR/clickup_performance.log"

if [ ! -f "$ENV_FILE" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: .env file not found at $ENV_FILE" >&2
    exit 1
fi

while IFS='=' read -r key value; do
    [[ $key =~ ^#.*$ ]] && continue
    [[ -z $key ]] && continue
    [[ -z $value ]] && continue
    
    key=$(echo "$key" | xargs)
    [[ -z $key ]] && continue
    
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"
    
    export "$key=$value"
done < <(grep -v '^[[:space:]]*$' "$ENV_FILE")

CRON_MAX_RETRIES=${CRON_MAX_RETRIES:-3}
CRON_RETRY_DELAY=${CRON_RETRY_DELAY:-300}
CRON_SEND_EMAIL=${CRON_SEND_EMAIL:-false}
CRON_ADMIN_EMAIL=${CRON_ADMIN_EMAIL:-""}
CRON_LOG_RETENTION_DAYS=${CRON_LOG_RETENTION_DAYS:-30}
DB_PORT=${DB_PORT:-3306}

mkdir -p "$LOG_DIR" 2>/dev/null
if [ ! -d "$LOG_DIR" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Cannot create log directory at $LOG_DIR" >&2
    exit 1
fi

log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" | tee -a "$LOG_FILE" "$ERROR_LOG"
}

send_error_email() {
    if [ "$CRON_SEND_EMAIL" = "true" ] && [ -n "$CRON_ADMIN_EMAIL" ]; then
        local subject="ClickUp Sync Failed - $(date '+%Y-%m-%d %H:%M:%S')"
        local body="$1\n\nLog file: $LOG_FILE\nError log: $ERROR_LOG"
        
        if command -v mail &> /dev/null; then
            echo -e "$body" | mail -s "$subject" "$CRON_ADMIN_EMAIL" 2>/dev/null
            [ $? -eq 0 ] && log_message "Error notification sent to $CRON_ADMIN_EMAIL"
        fi
    fi
}

check_lock() {
    if [ -f "$LOCK_FILE" ]; then
        local pid=$(cat "$LOCK_FILE" 2>/dev/null)
        if [ -n "$pid" ] && ps -p "$pid" > /dev/null 2>&1; then
            log_error "Another instance is running (PID: $pid). Exiting."
            exit 1
        else
            log_message "Stale lock file found. Removing."
            rm -f "$LOCK_FILE"
        fi
    fi
}

create_lock() {
    echo $$ > "$LOCK_FILE"
    if [ $? -eq 0 ]; then
        log_message "Lock file created (PID: $$)"
    else
        log_error "Failed to create lock file"
        exit 1
    fi
}

remove_lock() {
    [ -f "$LOCK_FILE" ] && rm -f "$LOCK_FILE" && log_message "Lock file removed"
}

cleanup() {
    remove_lock
    log_message "Cleanup completed"
}

check_environment() {
    log_message "Checking environment..."
    
    if [ ! -d "$VENV_PATH" ]; then
        log_error "Virtual environment not found at $VENV_PATH"
        return 1
    fi
    
    if [ ! -f "$VENV_PATH/bin/activate" ]; then
        log_error "Virtual environment activate script not found"
        return 1
    fi
    
    if [ ! -f "$PYTHON_SCRIPT" ]; then
        log_error "Python script not found at $PYTHON_SCRIPT"
        return 1
    fi
    
    if [ -z "$DB_HOST" ]; then
        log_error "DB_HOST missing in .env file"
        return 1
    fi
    
    if [ -z "$DB_NAME" ]; then
        log_error "DB_NAME missing in .env file"
        return 1
    fi
    
    if [ -z "$DB_USER" ]; then
        log_error "DB_USER missing in .env file"
        return 1
    fi
    
    if [ -z "$DB_PASSWORD" ]; then
        log_error "DB_PASSWORD missing in .env file"
        return 1
    fi
    
    if [ -z "$CLICKUP_API_TOKEN" ]; then
        log_error "CLICKUP_API_TOKEN missing in .env file"
        return 1
    fi
    
    log_message "Testing database connection to $DB_HOST:$DB_PORT/$DB_NAME..."
    
    if command -v mysql &> /dev/null; then
        MYSQL_CONFIG=$(mktemp)
        chmod 600 "$MYSQL_CONFIG"
        
        printf "[client]\n" > "$MYSQL_CONFIG"
        printf "host=%s\n" "$DB_HOST" >> "$MYSQL_CONFIG"
        printf "port=%s\n" "$DB_PORT" >> "$MYSQL_CONFIG"
        printf "user=%s\n" "$DB_USER" >> "$MYSQL_CONFIG"
        printf "password=%s\n" "$DB_PASSWORD" >> "$MYSQL_CONFIG"
        
        timeout 10 mysql --defaults-extra-file="$MYSQL_CONFIG" "$DB_NAME" -e "SELECT 1;" &> /dev/null
        local db_status=$?
        
        rm -f "$MYSQL_CONFIG"
        
        if [ $db_status -eq 0 ]; then
            log_message "✓ Database connection successful"
        elif [ $db_status -eq 124 ]; then
            log_error "Database connection timeout"
            return 1
        else
            log_error "Database connection failed (exit code: $db_status)"
            return 1
        fi
    else
        log_message "Warning: mysql command not found, skipping database connection test"
    fi
    
    log_message "✓ Environment check passed"
    return 0
}

rotate_logs() {
    log_message "Rotating logs..."
    
    if command -v find &> /dev/null; then
        local deleted_count=$(find "$LOG_DIR" -name "clickup_cron_*.log" -mtime +$CRON_LOG_RETENTION_DAYS -delete -print 2>/dev/null | wc -l)
        [ $deleted_count -gt 0 ] && log_message "Deleted $deleted_count old log file(s)"
    fi
    
    if [ -f "$ERROR_LOG" ]; then
        local size=$(stat -f%z "$ERROR_LOG" 2>/dev/null || stat -c%s "$ERROR_LOG" 2>/dev/null || echo 0)
        if [ "$size" -gt 10485760 ]; then
            mv "$ERROR_LOG" "$ERROR_LOG.$(date +%Y%m%d_%H%M%S)"
            touch "$ERROR_LOG"
            log_message "Error log rotated (size: $(($size / 1024 / 1024))MB)"
        fi
    fi
    
    if [ -f "$PERFORMANCE_LOG" ]; then
        local size=$(stat -f%z "$PERFORMANCE_LOG" 2>/dev/null || stat -c%s "$PERFORMANCE_LOG" 2>/dev/null || echo 0)
        if [ "$size" -gt 5242880 ]; then
            mv "$PERFORMANCE_LOG" "$PERFORMANCE_LOG.$(date +%Y%m%d_%H%M%S)"
            touch "$PERFORMANCE_LOG"
            log_message "Performance log rotated (size: $(($size / 1024 / 1024))MB)"
        fi
    fi
}

run_sync() {
    local attempt=$1
    local start_time=$(date +%s)
    
    log_message "Starting ClickUp sync (Attempt $attempt/$CRON_MAX_RETRIES)..."
    
    cd "$AUTOMATION_ROOT" || {
        log_error "Failed to change directory to $AUTOMATION_ROOT"
        return 1
    }
    
    source "$VENV_PATH/bin/activate" || {
        log_error "Failed to activate virtual environment"
        return 1
    }
    
    python "$PYTHON_SCRIPT" --auto >> "$LOG_FILE" 2>&1
    local exit_code=$?
    
    deactivate
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Duration: ${duration}s, Exit Code: $exit_code, Attempt: $attempt" >> "$PERFORMANCE_LOG"
    
    if [ $exit_code -eq 0 ]; then
        log_message "✓ Sync completed successfully in ${duration}s"
        return 0
    else
        log_error "Sync failed with exit code $exit_code (Duration: ${duration}s)"
        return $exit_code
    fi
}

log_message "========================================================================"
log_message "ClickUp Cron Job Started"
log_message "========================================================================"
log_message "Configuration:"
log_message "  Max Retries: $CRON_MAX_RETRIES"
log_message "  Retry Delay: ${CRON_RETRY_DELAY}s"
log_message "  Email Notifications: $CRON_SEND_EMAIL"
[ "$CRON_SEND_EMAIL" = "true" ] && log_message "  Admin Email: $CRON_ADMIN_EMAIL"
log_message "  Log Retention: ${CRON_LOG_RETENTION_DAYS} days"
log_message "  Database: $DB_HOST:$DB_PORT/$DB_NAME"
log_message "========================================================================"

trap cleanup EXIT INT TERM

check_lock
create_lock
rotate_logs

if ! check_environment; then
    log_error "Environment check failed. Exiting."
    send_error_email "ClickUp sync failed: Environment check failed.\n\nCheck logs at: $LOG_FILE"
    exit 1
fi

attempt=1
success=false

while [ $attempt -le $CRON_MAX_RETRIES ]; do
    if run_sync $attempt; then
        success=true
        break
    else
        if [ $attempt -lt $CRON_MAX_RETRIES ]; then
            log_message "Retrying in ${CRON_RETRY_DELAY}s..."
            sleep $CRON_RETRY_DELAY
        fi
    fi
    attempt=$((attempt + 1))
done

if [ "$success" = true ]; then
    log_message "✓ Cron job completed successfully"
    log_message "========================================================================"
    exit 0
else
    log_error "✗ Cron job failed after $CRON_MAX_RETRIES attempts"
    log_message "========================================================================"
    send_error_email "ClickUp sync failed after $CRON_MAX_RETRIES attempts.\n\nCheck logs at: $LOG_FILE\nError log: $ERROR_LOG"
    exit 1
fi
