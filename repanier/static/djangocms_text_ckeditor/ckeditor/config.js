/**
 * @license Copyright (c) 2003-2014, CKSource - Frederico Knabben. All rights reserved.
 * For licensing, see LICENSE.md or http://ckeditor.com/license
 */

CKEDITOR.editorConfig = function( config ) {
	// Define changes to default configuration here. For example:
	// config.language = 'fr';
	// config.uiColor = '#AADC6E';
};

// Remove default styles set
// CKEDITOR.stylesSet.add('default', []);
// IMPORTANT PCO : Allow epmty span tag needed for bootstrap glyficons
CKEDITOR.dtd.$removeEmpty.span = 0;
