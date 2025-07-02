# Cars.com Scraper with WordPress Integration

A web scraper for cars.com that saves data to CSV files and automatically updates WordPress databases via REST APIs. This system eliminates the need for direct database connections and provides a more flexible, production-ready solution.

## Features

- **CSV-Based Data Storage**: All scraped data is saved to CSV files for easy backup and portability
- **WordPress REST API Integration**: Automatic database updates via WordPress REST endpoints
- **No Direct Database Connections**: Works without requiring direct MySQL access
- **Automatic Data Synchronization**: CSV files automatically update WordPress database
- **Download Options**: Multiple ways to download CSV files
- **Live Site Compatible**: Works on production WordPress sites

## System Architecture

```
Python Scraper → CSV File → WordPress REST API → WordPress Database
     ↓              ↓              ↓                    ↓
  Scrapes      Saves Data    Updates DB          Displays Data
  Cars.com     to CSV       via REST API        via Shortcodes
```

## Installation

### 1. Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. WordPress Setup

1. Copy `wordpress_function.php` to your WordPress theme's `functions.php` file or create a custom plugin
2. The system will automatically create the necessary database table when first used

### 3. Configuration

Update the WordPress URL in `api/database.py`:

```python
WORDPRESS_URL = "https://your-wordpress-site.com"  # Update this
```

## Usage

### 1. Start the Python Server

```bash
cd api
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

### 2. WordPress Admin Interface

1. Go to your WordPress admin panel
2. Navigate to "Cars Data" in the admin menu
3. Use the "Run Scraper" page to configure and start scraping
4. Monitor progress and download CSV files

### 3. API Endpoints

- `POST /scrape/` - Start scraping with filters
- `GET /download-csv/` - Download the latest CSV file
- `GET /csv-info/` - Get information about the CSV file
- `GET /logs/` - View scraper logs
- `GET /health/` - Health check

### 4. WordPress REST API Endpoints

- `POST /wp-json/cars-scraper/v1/update-cars-data` - Update database with CSV data
- `GET /wp-json/cars-scraper/v1/get-cars-data` - Retrieve car data
- `GET /wp-json/cars-scraper/v1/download-csv` - Download CSV from WordPress
- `GET /wp-json/cars-scraper/v1/csv-info` - Get CSV information

## Data Flow

1. **Scraping**: Python scraper collects data from cars.com
2. **CSV Storage**: Data is saved to `cars_data.csv`
3. **WordPress Update**: CSV data is sent to WordPress via REST API
4. **Database Storage**: WordPress stores data in `wp_cars_data` table
5. **Display**: Data is displayed using WordPress shortcodes

## WordPress Shortcodes

Use `[cars_data_table]` to display scraped car data on any page or post.

## CSV Management

The system provides multiple ways to manage CSV files:

- **Automatic Downloads**: After scraping, download links are provided
- **CSV Management Page**: Dedicated page for CSV operations
- **REST API Downloads**: Download CSV files via WordPress REST API
- **Backup System**: Automatic backup of CSV files before updates

## Benefits

### For Development
- No database connection issues
- Easy data backup and restore
- Portable CSV files
- Simple debugging

### For Production
- Works on live WordPress sites
- No direct database access required
- Automatic data synchronization
- Multiple download options

## File Structure

```
├── api/
│   ├── database.py      # CSV operations and WordPress REST API
│   ├── scraper.py       # Main scraping logic
│   ├── server.py        # FastAPI server
│   └── logs/
│       └── error.log    # Error logging
├── cars_data.csv        # Scraped data storage
├── wordpress_function.php # WordPress integration
└── requirements.txt     # Python dependencies
```

## Troubleshooting

### Common Issues

1. **WordPress REST API Not Accessible**
   - Check if WordPress is running
   - Verify REST API is enabled
   - Check CORS settings

2. **CSV File Not Found**
   - Run the scraper first
   - Check file permissions
   - Verify file path

3. **Scraping Errors**
   - Check logs at `/logs/`
   - Verify internet connection
   - Check if cars.com is accessible

### Logs

- Python logs: `api/logs/error.log`
- WordPress logs: Check WordPress debug log
- API logs: Available via `/logs/` endpoint

## Security Considerations

- WordPress REST API endpoints require admin permissions
- CSV files are stored locally
- No sensitive database credentials in code
- CORS is configured for local development

## Production Deployment

1. Update `WORDPRESS_URL` in `api/database.py`
2. Configure proper CORS settings
3. Set up proper file permissions for CSV storage
4. Use HTTPS for production
5. Configure proper logging

## License

This project is licensed under the MIT License.