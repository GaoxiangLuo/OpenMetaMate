module.exports = {
  hooks: {
    readPackage(pkg) {
      // Fix peer dependencies for React 19 compatibility
      if (pkg.name === "react-day-picker" || pkg.name === "vaul") {
        if (pkg.peerDependencies?.react) {
          pkg.peerDependencies.react = "^16.8.0 || ^17.0.0 || ^18.0.0 || ^19.0.0"
        }
        if (pkg.peerDependencies?.["react-dom"]) {
          pkg.peerDependencies["react-dom"] = "^16.8.0 || ^17.0.0 || ^18.0.0 || ^19.0.0"
        }
      }
      return pkg
    },
  },
}
