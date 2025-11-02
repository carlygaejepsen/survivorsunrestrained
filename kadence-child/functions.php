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
 * Child theme setup.
 */
function survivors_unrestrained_child_theme_setup() {
	/**
	 * Enqueue parent/child styles.
	 */
	function survivors_child_enqueue_styles() {
		$theme      = wp_get_theme();
		$parent     = $theme->parent();
		$parent_dep = array();

		if ( $parent ) {
			wp_enqueue_style(
				'survivors-parent-style',
				get_template_directory_uri() . '/style.css',
				array(),
				$parent->get( 'Version' )
			);
			$parent_dep[] = 'survivors-parent-style';
		}

		wp_enqueue_style(
			'survivors-child-style',
			get_stylesheet_uri(),
			$parent_dep,
			$theme->get( 'Version' ) ? $theme->get( 'Version' ) : SU_CHILD_THEME_VERSION
		);
	}
	add_action( 'wp_enqueue_scripts', 'survivors_child_enqueue_styles' );

	/**
	 * Enqueue Food Pantry Resource Browser assets only when needed.
	 */
	function survivors_resource_browser_assets() {
		if ( ! is_page_template( 'templates/page-food-pantry-resource-browser.php' ) ) {
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

		wp_enqueue_style(
			'su-resource-browser',
			get_stylesheet_directory_uri() . '/assets/css/pantry-resource-browser.css',
			array( 'survivors-child-style' ),
			SU_CHILD_THEME_VERSION
		);

		wp_enqueue_script(
			'su-resource-browser',
			get_stylesheet_directory_uri() . '/assets/js/pantry-resource-browser.js',
			array( 'su-tailwind' ),
			SU_CHILD_THEME_VERSION,
			true
		);

		$datasets_path = trailingslashit( get_stylesheet_directory() ) . 'assets/datasets';
		$datasets_url  = trailingslashit( get_stylesheet_directory_uri() ) . 'assets/datasets';

		$states = array();
		if ( is_dir( $datasets_path ) ) {
			$dataset_files = glob( $datasets_path . '/*_food_pantries_*.json' );

			if ( ! empty( $dataset_files ) ) {
				foreach ( $dataset_files as $file ) {
					$filename = basename( $file );

					if ( preg_match( '/^([a-z]{2})_food_pantries_/i', $filename, $matches ) ) {
						$states[] = strtolower( $matches[1] );
					}
				}

				$states = array_unique( $states );
				sort( $states );
			}
		}

		wp_localize_script(
			'su-resource-browser',
			'suResourceBrowser',
			array(
				'datasetsBaseUrl' => $datasets_url,
				'states'          => array_values( $states ),
				'cacheBuster'     => SU_CHILD_THEME_VERSION,
				'i18n'            => array(
					'chooseState' => __( 'Choose State', 'survivors-child' ),
					'stateLabel'  => __( 'Select a State:', 'survivors-child' ),
					'searchLabel' => __( 'Filter by Name or City:', 'survivors-child' ),
					'noDatasets'  => __( 'No datasets available', 'survivors-child' ),
				),
			)
		);
	}
	add_action( 'wp_enqueue_scripts', 'survivors_resource_browser_assets' );

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
	add_filter( 'theme_page_templates', 'survivors_register_resource_browser_template' );

	/**
	 * Load the Resource Browser template on the front end when it's assigned.
	 *
	 * @param string $template Path to the template WordPress is about to use.
	 *
	 * @return string
	 */
	function survivors_load_resource_browser_template( $template ) {
		if ( is_page() ) {
			$page_template = get_page_template_slug( get_queried_object_id() );

			if ( 'templates/page-food-pantry-resource-browser.php' === $page_template ) {
				$child_template = get_stylesheet_directory() . '/templates/page-food-pantry-resource-browser.php';

				if ( file_exists( $child_template ) ) {
					return $child_template;
				}
			}
		}

		return $template;
	}
	add_filter( 'template_include', 'survivors_load_resource_browser_template' );
}
add_action( 'after_setup_theme', 'survivors_unrestrained_child_theme_setup' );
