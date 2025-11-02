<?php
/**
 * The main template file
 *
 * This template simply loads the parent theme's index.php file.
 * Child themes should delegate to the parent theme unless overriding specific functionality.
 *
 * @package survivors-unrestrained-child
 */

// Load the parent theme's index.php template.
$parent_template = get_template_directory() . '/index.php';

if ( file_exists( $parent_template ) ) {
	include $parent_template;
} else {
	// Emergency fallback if parent theme is missing.
	wp_die(
		'<h1>Theme Configuration Error</h1>' .
		'<p>The parent theme (Kadence) could not be found. Please ensure:</p>' .
		'<ol>' .
		'<li>The Kadence theme is installed in: <code>/wp-content/themes/kadence/</code></li>' .
		'<li>The parent theme is not deleted or renamed</li>' .
		'<li>File permissions are correct</li>' .
		'</ol>' .
		'<p><a href="' . admin_url( 'themes.php' ) . '">Go to Themes</a></p>',
		'Theme Error',
		array( 'back_link' => true )
	);
}
