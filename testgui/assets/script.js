var failedStatuses = ['error', 'failure']
app = new Vue({
    el: '#q-app',
    data: function () {
      return {
        tests: {},
        expandProblems: true,
        reloadModules: true,
        loadingTests: true,
      }
    },
    filters: {
        statusIcon: function(test){
            return {
              notRun: 'play_arrow',
              success: 'done',
              error: 'error',
              failure: 'highlight_off',
            }[test.status]
        },
        statusColor: function(test){
            return {
              notRun: 'text-black',
              success: 'text-positive',
              error: 'text-warning',
              failure: 'text-negative'
            }[test.status]
        }
    },
    computed: {
        anyTestRunning(){
            return _.some(this.tests, test=>test.status === 'running')
        },
        allSuccess(){
            return this.nStatuses['success']>0 && _.keys(this.nStatuses).length === 1
        },
        nStatuses(){
            return _.countBy(this.tests, test=>test.status)
        }
    },
    watch: {
        expandProblems: function(expand){
            _.each(this.tests, test => {
                this.$set(test, 'expand', expand ? failedStatuses.includes(test.status) : undefined)
            })
        }
    },
    methods: {
        repopulateTests(){
            this.tests = {}
            this.loadingTests = true
            window.pywebview.api.repopulate_tests()
        },
        runAllTests(){
            _.each(this.tests, t=>{t.status='running'})
            window.pywebview.api.run_all_tests()
        },
        runFailedTests(){
            var failedTests = _.filter(this.tests, test=>failedStatuses.includes(test.status))
            this.runTests(failedTests)
        },
        runTests(tests){
            _.each(tests, t=>{t.status='running'})
            window.pywebview.api.run_selected_tests(
                _.map(tests, test => test.index)
            )
        },
        setHover(test, hover){
            this.$set(test, 'hover', hover)
        },
        setTestStatus(test, status){
            this.$set(test, 'status', status)
            if(this.expandProblems){
                this.$set(test,'expand', ['error', 'failure'].includes(test.status))
            }
        }
    },
})
function initTests(tests){
  app.$set(app._data, 'tests', {})
  tests.forEach((e, i)=>{
    var name = e.join('.')
    app.$set(
        app._data.tests, name, {
        path: e,
        index: i,
    })
    app.setTestStatus(app._data.tests[name], 'notRun')
  })
  app._data.loadingTests = false
}
function setResult({name, message, status}){
    app.setTestStatus(app._data.tests[name], status)
    app._data.tests[name].message = message
}
function setWarning({message}){
    const longTimeOut = 7000
    app.$q.notify({
        type: 'warning',
        timeout: longTimeOut,
        position: 'top',
        message: message,
        multiline: true,
    })
}