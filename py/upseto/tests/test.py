import unittest
import gitwrapper
import upsetowrapper
import upseto.manifest
import os
import shutil


class Test(unittest.TestCase):
    def setUp(self):
        gitwrapper.setUp()

    def tearDown(self):
        gitwrapper.tearDown()

    class SimpleManifest_OneProjectDependsOnTwoOthers:
        def __init__(self, test):
            self.project1 = gitwrapper.GitHub("project1")
            self.project2 = gitwrapper.GitHub("project2")
            self.requiringProject = gitwrapper.GitHub("requiringProject")

            self.localClone1 = gitwrapper.LocalClone(self.project1)
            self.localClone2 = gitwrapper.LocalClone(self.project2)
            self.localRequiringProject = gitwrapper.LocalClone(self.requiringProject)
            test.assertEquals(self.project1.hash('master'), self.localClone1.hash())
            test.assertEquals(self.project2.hash('master'), self.localClone2.hash())
            test.assertEquals(self.requiringProject.hash(), self.localRequiringProject.hash())

            upsetowrapper.run(self.localRequiringProject, "addRequirement project1")
            upsetowrapper.run(self.localRequiringProject, "addRequirement project2")
            test.assertTrue(os.path.exists(self.localRequiringProject.manifestFilename()))
            self.localRequiringProject.addCommitPushManifest()

            self.manifest = upseto.manifest.Manifest.fromDir(self.localRequiringProject.directory())
            requirements = self.manifest.requirements()
            test.assertEquals(len(requirements), 2)
            test.assertEquals(requirements[0]['originURL'], "file://" + self.project1.directory())
            test.assertEquals(requirements[0]['hash'], self.project1.hash())
            test.assertEquals(requirements[1]['originURL'], "file://" + self.project2.directory())
            test.assertEquals(requirements[1]['hash'], self.project2.hash())

        def addThirdTier(self):
            self.recursiveProject = gitwrapper.GitHub("recursiveProject")
            self.localRecursiveProject = gitwrapper.LocalClone(self.recursiveProject)
            upsetowrapper.run(self.localRecursiveProject, "addRequirement requiringProject")
            self.localRecursiveProject.addCommitPushManifest()

    def test_simpleManifest_OneProjectDependsOnTwoOthers_RequirementsFetched(self):
        case = self.SimpleManifest_OneProjectDependsOnTwoOthers(self)

        shutil.rmtree(gitwrapper.localClonesDir())

        localRequiringProject = gitwrapper.LocalClone(case.requiringProject)
        upsetowrapper.run(localRequiringProject, "fulfillRequirements")
        self.assertEquals(case.project1.hash('master'), case.localClone1.hash())
        self.assertEquals(case.project2.hash('master'), case.localClone2.hash())
        self.assertEquals(case.requiringProject.hash('master'), case.localRequiringProject.hash())

    def test_simpleManifest_NothingToBeDone(self):
        case = self.SimpleManifest_OneProjectDependsOnTwoOthers(self)

        upsetowrapper.run(case.localRequiringProject, "fulfillRequirements")
        self.assertEquals(case.project1.hash('master'), case.localClone1.hash())
        self.assertEquals(case.project2.hash('master'), case.localClone2.hash())
        self.assertEquals(case.requiringProject.hash('master'), case.localRequiringProject.hash())

    def test_checkRequirements(self):
        case = self.SimpleManifest_OneProjectDependsOnTwoOthers(self)

        upsetowrapper.run(case.localRequiringProject, "checkRequirements")
        shutil.rmtree(case.localClone2.directory())
        upsetowrapper.runShouldFail(case.localRequiringProject, "checkRequirements", "exist")

    def test_simpleManifest_DetachedVersion(self):
        case = self.SimpleManifest_OneProjectDependsOnTwoOthers(self)

        hashBefore = case.localClone1.hash()
        case.localClone1.createAddCommitPush('anotherfile')
        hashAfter = case.localClone1.hash()
        self.assertNotEqual(hashBefore, hashAfter)

        upsetowrapper.run(case.localRequiringProject, "fulfillRequirements")
        self.assertEquals(case.localClone1.hash(), hashBefore)
        self.assertEquals(case.project2.hash('master'), case.localClone2.hash())
        self.assertEquals(case.requiringProject.hash('master'), case.localRequiringProject.hash())

    def test_recursiveRequirements(self):
        case = self.SimpleManifest_OneProjectDependsOnTwoOthers(self)
        case.addThirdTier()

        shutil.rmtree(gitwrapper.localClonesDir())
        localRecursiveProject = gitwrapper.LocalClone(case.recursiveProject)
        upsetowrapper.run(localRecursiveProject, "fulfillRequirements")
        self.assertEquals(case.requiringProject.hash('master'), case.localRequiringProject.hash())
        self.assertEquals(case.project1.hash('master'), case.localClone1.hash())
        self.assertEquals(case.project2.hash('master'), case.localClone2.hash())

    def test_recursiveRequirementDirectlyRequiresFirstLayerProject(self):
        case = self.SimpleManifest_OneProjectDependsOnTwoOthers(self)
        case.addThirdTier()

        upsetowrapper.run(case.localRecursiveProject, "addRequirement project1")
        case.localRecursiveProject.addCommitPushManifest()

        shutil.rmtree(gitwrapper.localClonesDir())
        localRecursiveProject = gitwrapper.LocalClone(case.recursiveProject)
        upsetowrapper.run(localRecursiveProject, "fulfillRequirements")
        self.assertEquals(case.requiringProject.hash('master'), case.localRequiringProject.hash())
        self.assertEquals(case.project1.hash('master'), case.localClone1.hash())
        self.assertEquals(case.project2.hash('master'), case.localClone2.hash())

    def test_refusesToCreateHashInconsistency_TwoProjectPointAtSameOriginWithDifferentHashes(self):
        case = self.SimpleManifest_OneProjectDependsOnTwoOthers(self)
        case.addThirdTier()

        case.localClone1.createAddCommitPush("anotherfile")
        upsetowrapper.runShouldFail(case.localRecursiveProject, "addRequirement project1", "hash paradox")
        upsetowrapper.runShouldFail(case.localRecursiveProject, "checkRequirements", "hash")
        upsetowrapper.run(case.localRecursiveProject, "fulfillRequirements")
        upsetowrapper.run(case.localRecursiveProject, "checkRequirements")
        upsetowrapper.run(case.localRecursiveProject, "addRequirement project1")

    def test_updateVersion(self):
        case = self.SimpleManifest_OneProjectDependsOnTwoOthers(self)

        case.localClone1.createAddCommitPush("anotherfile")
        newHash = case.localClone1.hash()

        upsetowrapper.runShouldFail(case.localRequiringProject, "checkRequirements", "hash")
        upsetowrapper.run(case.localRequiringProject, "fulfillRequirements")
        upsetowrapper.run(case.localRequiringProject, "checkRequirements")
        self.assertNotEqual(case.localClone1.hash(), newHash)

        case.localClone1.checkout('master')
        self.assertEqual(case.localClone1.hash(), newHash)
        upsetowrapper.run(case.localRequiringProject, "addRequirement project1")
        upsetowrapper.run(case.localRequiringProject, "checkRequirements")
        self.assertEqual(case.localClone1.hash(), newHash)

    def test_circle(self):
        case = self.SimpleManifest_OneProjectDependsOnTwoOthers(self)
        case.addThirdTier()

        upsetowrapper.runShouldFail(case.localClone1, "addRequirement recursiveProject", "circle")

        upsetowrapper.run(case.localRecursiveProject, "delRequirement requiringProject")
        upsetowrapper.run(case.localClone1, "addRequirement recursiveProject")
        upsetowrapper.runShouldFail(case.localRecursiveProject, "addRequirement requiringProject", "circle")

    def test_show(self):
        case = self.SimpleManifest_OneProjectDependsOnTwoOthers(self)
        case.addThirdTier()
        result = upsetowrapper.run(case.localRecursiveProject, "checkRequirements --show")
        print result

# test no project can be added file not found or not git
# test can not remove
# test basenames collision
# test manifest files must not be in modified state - either committed or unknown

if __name__ == '__main__':
    unittest.main()
