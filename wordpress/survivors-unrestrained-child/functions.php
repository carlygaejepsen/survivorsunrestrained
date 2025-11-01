<?php
/**
 * Survivors Unrestrained child theme bootstrap.
 */

define( 'SU_CHILD_THEME_VERSION', '1.0.0' );

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
        array(),
        SU_CHILD_THEME_VERSION,
        true
    );

    $datasets_dir = trailingslashit( get_stylesheet_directory_uri() ) . 'assets/datasets';

    wp_localize_script(
        'su-resource-browser',
        'suResourceBrowser',
        array(
            'datasetsBaseUrl' => $datasets_dir,
            'states'          => array( 'ak', 'al', 'ar', 'az', 'ca', 'co', 'ct', 'dc', 'de', 'fl', 'ga' ),
            'i18n'            => array(
                'chooseState' => __( 'Choose State', 'survivors-child' ),
                'stateLabel'  => __( 'Select a State:', 'survivors-child' ),
                'searchLabel' => __( 'Filter by Name or City:', 'survivors-child' )
            )
        )
    );
}
add_action( 'wp_enqueue_scripts', 'survivors_resource_browser_assets' );
