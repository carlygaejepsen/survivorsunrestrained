<?php
/**
 * Survivors Unrestrained child theme bootstrap.
 *
 * @package survivors-unrestrained-child
 */

if ( ! defined( 'SU_CHILD_THEME_VERSION' ) ) {
	define( 'SU_CHILD_THEME_VERSION', '1.0.1' );
}

/**
 * Enqueue parent/child styles.
 */
function survivors_child_enqueue_styles() {
	$theme  = wp_get_theme();
	$parent = $theme->parent();

	// It's best practice to load the parent theme's stylesheet.
	// Kadence handles this, but it's good to have for other themes.
	wp_enqueue_style(
		'survivors-parent-style',
		get_template_directory_uri() . '/style.css',
		array(),
		$parent ? $parent->get( 'Version' ) : ''
	);

	wp_enqueue_style(
		'survivors-child-style',
		get_stylesheet_uri(),
		array( 'survivors-parent-style' ),
		$theme->get( 'Version' ) ? $theme->get( 'Version' ) : SU_CHILD_THEME_VERSION
	);
}

/**
 * Determine whether the current request is rendering the Food Pantry Resource Browser page.
 *
 * @return bool
 */
function survivors_is_resource_browser_page() {
    if ( ! is_singular( 'page' ) ) {
        return false;
    }

    $queried_id = get_queried_object_id();
    if ( ! $queried_id ) {
        return false;
    }

    $template = get_page_template_slug( $queried_id );

    return 'templates/page-food-pantry-resource-browser.php' === $template;
}

/**
 * Enqueue Food Pantry Resource Browser assets only when needed.
 */
function survivors_resource_browser_assets() {
    if ( ! survivors_is_resource_browser_page() ) {
        return;
    }

    // Tailwind CDN with custom config.
    wp_register_script( 'su-tailwind', 'https://cdn.tailwindcss.com', array(), null, true );
    $tailwind_config = <<<'JS'
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        primary: '#4CAF50',
                        secondary: '#FF9800',
                        background: '#f4f7f6',
                        card: '#ffffff'
                    },
                    fontFamily: {
                        sans: ['Inter', 'sans-serif']
                    }
                }
            }
        };
    JS;
    wp_add_inline_script( 'su-tailwind', $tailwind_config, 'before' );
    wp_enqueue_script( 'su-tailwind' );

    // Use file modification time for effective cache busting.
    $js_version = file_exists( get_stylesheet_directory() . '/assets/js/pantry-resource-browser.js' )
        ? filemtime( get_stylesheet_directory() . '/assets/js/pantry-resource-browser.js' )
        : SU_CHILD_THEME_VERSION;


    $resource_css_path = get_stylesheet_directory() . '/assets/css/pantry-resource-browser.css';
    $resource_css_version = file_exists( $resource_css_path ) ? filemtime( $resource_css_path ) : SU_CHILD_THEME_VERSION;

    wp_enqueue_style(
        'su-resource-browser',
        get_stylesheet_directory_uri() . '/assets/css/pantry-resource-browser.css',
        array( 'survivors-child-style' ),
        $resource_css_version
    );

    wp_enqueue_script(
        'su-resource-browser',
        get_stylesheet_directory_uri() . '/assets/js/pantry-resource-browser.js',
        array( 'su-tailwind' ),
        $js_version,
        true
    );

		$datasets_path = trailingslashit( get_stylesheet_directory() ) . 'assets/datasets';
		$datasets_url  = trailingslashit( get_stylesheet_directory_uri() ) . 'assets/datasets';

    $datasets = array();

    if ( is_dir( $datasets_path ) ) {
        $dataset_files = glob( $datasets_path . '/*_food_pantries_*.json' );

        if ( is_array( $dataset_files ) && ! empty( $dataset_files ) ) {
            // Find all dataset files and group them by state.
            foreach ( $dataset_files as $file ) {
                if ( preg_match( '/^([a-z]{2})_food_pantries_(\d+)\.json$/i', basename( $file ), $matches ) ) {
                    $state = strtolower( $matches[1] );
                    if ( ! isset( $datasets[ $state ] ) ) {
                        $datasets[ $state ] = array();
                    }
                    $datasets[ $state ][] = basename( $file );
                }
            }

            // For each state, find the file with the highest version number.
            $final_datasets = array();
            foreach ( $datasets as $state => $files ) {
                if ( is_array( $files ) && ! empty( $files ) ) {
                    natsort( $files );
                    $final_datasets[ $state ] = end( $files );
                }
            }
            $datasets = $final_datasets;
        }
    }

    wp_localize_script(
        'su-resource-browser',
        'suResourceBrowser',
        array(
            'datasetsBaseUrl' => $datasets_url,
            'datasets'        => $datasets,
            'cacheBuster'     => SU_CHILD_THEME_VERSION,
            'i18n'            => array(
                'chooseState' => __( 'Choose State', 'survivors-child' ),
                'stateLabel'  => __( 'Select a State:', 'survivors-child' ),
                'searchLabel' => __( 'Filter by Name or City:', 'survivors-child' ),
                'noDatasets'  => __( 'No datasets available', 'survivors-child' ),
            )
        )
    );
}

	/**
	 * Register the Food Pantry Resource Browser template when editing pages.
	 *
	 * @param array $templates Existing page templates.
	 *
	 * @return array
	 */
	function survivors_register_resource_browser_template( $templates ) {
		$templates['templates/page-food-pantry-resource-browser.php'] = __( 'Food Pantry Resource Browser', 'survivors-child' );

		return $templates;
	}

/**
 * Load the Resource Browser template on the front end when it's assigned.
 *
 * @param string $template Path to the template WordPress is about to use.
 *
 * @return string
 */
function survivors_load_resource_browser_template( $template ) {
    if ( survivors_is_resource_browser_page() ) {
        $child_template = get_stylesheet_directory() . '/templates/page-food-pantry-resource-browser.php';

        if ( file_exists( $child_template ) ) {
            return $child_template;
        }
    }

		return $template;
	}

/**
 * Set up child theme hooks.
 */
add_action( 'wp_enqueue_scripts', 'survivors_child_enqueue_styles' );
add_action( 'wp_enqueue_scripts', 'survivors_resource_browser_assets' );
add_filter( 'theme_page_templates', 'survivors_register_resource_browser_template' );
add_filter( 'template_include', 'survivors_load_resource_browser_template' );
