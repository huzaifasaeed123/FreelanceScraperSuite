import sqlite3
import dataset
import logging
import os
# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_connection_table(db_path='bricklink_parse.db'):
    """Create a connection table for the three basic relationships"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Set SQLite pragmas for better performance
        cursor.execute("PRAGMA journal_mode=DELETE")  # Use DELETE mode instead of WAL to avoid huge WAL files
        cursor.execute("PRAGMA synchronous=NORMAL")   # Faster writes
        cursor.execute("PRAGMA temp_store=MEMORY")    # Use memory for temp tables
        cursor.execute("PRAGMA cache_size=-64000")    # 64MB cache
        
        # Create the connection table
        logger.info("Creating connection table...")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS connection_table (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                set_id TEXT,
                minifigure_id TEXT,
                part_id TEXT,
                FOREIGN KEY (set_id) REFERENCES set_parse(item_number),
                FOREIGN KEY (minifigure_id) REFERENCES minifigures_parse(item_number),
                FOREIGN KEY (part_id) REFERENCES part_parse(item_number)
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_set_id ON connection_table(set_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_minifigure_id ON connection_table(minifigure_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_part_id ON connection_table(part_id)")
        
        # Create indexes for part_parse_color table if needed
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_part_color_item_number ON part_parse_color(item_number)
            WHERE EXISTS (SELECT 1 FROM sqlite_master WHERE type='table' AND name='part_parse_color')
        """)
        
        conn.commit()
        logger.info("Connection table created successfully!")
        
    except Exception as e:
        logger.error(f"Error creating connection table: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def populate_connection_table_batch(db_path='bricklink_parse.db', batch_size=1000):
    """Populate the connection table with batch processing"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Set SQLite pragmas
        cursor.execute("PRAGMA journal_mode=DELETE")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA cache_size=-64000")
        
        # Clear existing data
        logger.info("Clearing existing connection table data...")
        cursor.execute("DELETE FROM connection_table")
        conn.commit()
        
        # Process sets table
        logger.info("Processing sets relationships...")
        cursor.execute("SELECT item_number, parts_relation, minifigs_relation FROM set_parse")
        sets_data = cursor.fetchall()
        
        batch_data = []
        total_processed = 0
        
        for set_row in sets_data:
            set_id = set_row[0]
            parts_relation = set_row[1]
            minifigs_relation = set_row[2]
            
            # Process parts relation
            if parts_relation:
                parts = [p.strip() for p in parts_relation.split(',') if p.strip()]
                for part_id in parts:
                    batch_data.append((set_id, None, part_id))
                    
                    if len(batch_data) >= batch_size:
                        insert_batch(cursor, batch_data)
                        conn.commit()
                        batch_data = []
                        total_processed += batch_size
                        logger.info(f"Processed {total_processed} relations...")
            
            # Process minifigures relation
            if minifigs_relation:
                minifigs = [m.strip() for m in minifigs_relation.split(',') if m.strip()]
                for minifig_id in minifigs:
                    batch_data.append((set_id, minifig_id, None))
                    
                    if len(batch_data) >= batch_size:
                        insert_batch(cursor, batch_data)
                        conn.commit()
                        batch_data = []
                        total_processed += batch_size
                        logger.info(f"Processed {total_processed} relations...")
        
        # Process minifigures table
        logger.info("Processing minifigures relationships...")
        cursor.execute("SELECT item_number, parts_relation FROM minifigures_parse")
        minifigs_data = cursor.fetchall()
        
        for minifig_row in minifigs_data:
            minifig_id = minifig_row[0]
            parts_relation = minifig_row[1]
            
            # Process parts relation
            if parts_relation:
                parts = [p.strip() for p in parts_relation.split(',') if p.strip()]
                for part_id in parts:
                    batch_data.append((None, minifig_id, part_id))
                    
                    if len(batch_data) >= batch_size:
                        insert_batch(cursor, batch_data)
                        conn.commit()
                        batch_data = []
                        total_processed += batch_size
                        logger.info(f"Processed {total_processed} relations...")
        
        # Insert any remaining data
        if batch_data:
            insert_batch(cursor, batch_data)
            conn.commit()
            total_processed += len(batch_data)
        
        logger.info(f"Connection table populated successfully! Total relations: {total_processed}")
        
        # Vacuum to reclaim space
        logger.info("Vacuuming database...")
        cursor.execute("VACUUM")
        
    except Exception as e:
        logger.error(f"Error populating connection table: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def insert_batch(cursor, batch_data):
    """Insert a batch of data"""
    cursor.executemany("""
        INSERT INTO connection_table (set_id, minifigure_id, part_id)
        VALUES (?, ?, ?)
    """, batch_data)

def fix_wal_issue(db_path='bricklink_parse.db'):
    """Fix the WAL file issue by checkpointing and switching journal mode"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        logger.info("Fixing WAL issue...")
        
        # First, checkpoint the WAL file to merge it back
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        
        # Switch to DELETE journal mode to avoid WAL issues
        cursor.execute("PRAGMA journal_mode=DELETE")
        
        # Vacuum to reclaim space
        logger.info("Vacuuming database...")
        cursor.execute("VACUUM")
        
        conn.commit()
        logger.info("WAL issue fixed!")
        
    except Exception as e:
        logger.error(f"Error fixing WAL issue: {e}")
        raise
    finally:
        conn.close()

def verify_statistics(db_path='bricklink_parse.db'):
    """Show statistics about the connection table and other tables"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Total count of connection table
        cursor.execute("SELECT COUNT(*) FROM connection_table")
        total = cursor.fetchone()[0]
        
        # Different relationship types
        cursor.execute("""
            SELECT 
                COUNT(CASE WHEN set_id IS NOT NULL AND part_id IS NOT NULL AND minifigure_id IS NULL THEN 1 END) as set_part,
                COUNT(CASE WHEN set_id IS NOT NULL AND minifigure_id IS NOT NULL AND part_id IS NULL THEN 1 END) as set_minifig,
                COUNT(CASE WHEN minifigure_id IS NOT NULL AND part_id IS NOT NULL AND set_id IS NULL THEN 1 END) as minifig_part
            FROM connection_table
        """)
        
        stats = cursor.fetchone()
        
        logger.info("\nConnection table statistics:")
        logger.info(f"Total connections: {total}")
        logger.info(f"Set-Part relations: {stats[0]}")
        logger.info(f"Set-Minifigure relations: {stats[1]}")
        logger.info(f"Minifigure-Part relations: {stats[2]}")
        
        # Check if part_parse_color table exists and show stats
        cursor.execute("""
            SELECT COUNT(*) FROM sqlite_master 
            WHERE type='table' AND name='part_parse_color'
        """)
        
        if cursor.fetchone()[0] > 0:
            cursor.execute("SELECT COUNT(*) FROM part_parse_color")
            color_count = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(DISTINCT item_number) FROM part_parse_color
            """)
            unique_parts = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(DISTINCT color) FROM part_parse_color
            """)
            unique_colors = cursor.fetchone()[0]
            
            logger.info("\nPart color statistics:")
            logger.info(f"Total color entries: {color_count}")
            logger.info(f"Unique parts with color data: {unique_parts}")
            logger.info(f"Unique colors: {unique_colors}")
            
            # Top 5 colors by occurrence
            cursor.execute("""
                SELECT color, COUNT(*) as count 
                FROM part_parse_color 
                GROUP BY color 
                ORDER BY count DESC 
                LIMIT 5
            """)
            
            logger.info("\nTop 5 colors by occurrence:")
            for color, count in cursor.fetchall():
                logger.info(f"{color}: {count} occurrences")
        
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
    finally:
        conn.close()

def export_parts_colors_data(db_path='bricklink_parse.db', output_path='output/parts_colors_data.xlsx'):
    """Export parts color data to Excel with analysis"""
    try:
        import pandas as pd
        
        # Connect to database
        conn = sqlite3.connect(db_path)
        
        # Query for parts with their colors
        query = """
            SELECT p.item_number, p.item_name, p.category, pc.color, pc.appears_as, 
                   pc.in_sets, pc.total_qty
            FROM part_parse p
            JOIN part_parse_color pc ON p.item_number = pc.item_number
            ORDER BY p.item_number, pc.color
        """
        
        # Load data into DataFrame
        logger.info("Loading parts colors data for export...")
        df = pd.read_sql_query(query, conn)
        
        # Export to Excel
        logger.info(f"Exporting parts colors data to {output_path}...")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df.to_excel(output_path, index=False)
        
        # Summary stats
        logger.info(f"Exported {len(df)} color entries for {df['item_number'].nunique()} parts")
        
    except Exception as e:
        logger.error(f"Error exporting parts colors data: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    # First, fix the WAL issue
    fix_wal_issue()
    
    # Create the connection table
    create_connection_table()
    
    # Populate with batch processing
    populate_connection_table_batch(batch_size=1000)
    
    # Show statistics
    verify_statistics()
    
    # Export parts colors data
    export_parts_colors_data()