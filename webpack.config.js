var Encore = require('@symfony/webpack-encore');

Encore
    // directory where compiled assets will be stored
    .setOutputPath('./repanier/static/repanier/alois')
    // public path used by the web server to access the output path
    .setPublicPath('/static')
    .enableSingleRuntimeChunk()
    .addStyleEntry('bootstrap/css/bootstrap', './repanier/static/repanier/alois/scss/custom-bootstrap.scss')
    .addStyleEntry('css/custom', './repanier/static/repanier/alois/scss/main.scss')
    .addStyleEntry('css/custom_admin', './repanier/static/repanier/alois/scss/custom_admin.scss')
    .enableSassLoader()
;

module.exports = Encore.getWebpackConfig();
